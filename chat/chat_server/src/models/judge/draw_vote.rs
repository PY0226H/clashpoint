use super::*;

impl AppState {
    fn is_unique_violation(err: &sqlx::Error) -> bool {
        matches!(
            err,
            sqlx::Error::Database(db_err) if db_err.code().as_deref() == Some("23505")
        )
    }

    async fn load_draw_vote_stats(
        tx: &mut Transaction<'_, Postgres>,
        vote_id: i64,
    ) -> Result<DrawVoteStatsRow, AppError> {
        let stats = sqlx::query_as(
            r#"
            SELECT
                COUNT(*)::integer AS participated_voters,
                COUNT(*) FILTER (WHERE agree_draw)::integer AS agree_votes,
                COUNT(*) FILTER (WHERE NOT agree_draw)::integer AS disagree_votes
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1
            "#,
        )
        .bind(vote_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(stats)
    }

    async fn maybe_finalize_draw_vote(
        tx: &mut Transaction<'_, Postgres>,
        vote: DrawVoteRow,
        stats: &DrawVoteStatsRow,
    ) -> Result<DrawVoteRow, AppError> {
        if vote.status != "open" {
            return Ok(vote);
        }
        let now = Utc::now();
        let decision = if stats.participated_voters >= vote.required_voters {
            Some((
                "decided",
                majority_resolution(stats.agree_votes, stats.disagree_votes),
            ))
        } else if vote.voting_ends_at <= now {
            Some(("expired", "open_rematch"))
        } else {
            None
        };
        let Some((status, resolution)) = decision else {
            return Ok(vote);
        };
        let vote = if resolution == "open_rematch" {
            Self::ensure_rematch_session_for_vote(tx, vote).await?
        } else {
            vote
        };
        let updated: DrawVoteRow = sqlx::query_as(
            r#"
            UPDATE judge_draw_votes
            SET status = $2,
                resolution = $3,
                decided_at = $4,
                updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, session_id, final_report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            "#,
        )
        .bind(vote.id)
        .bind(status)
        .bind(resolution)
        .bind(Some(now))
        .fetch_one(&mut **tx)
        .await?;
        Ok(updated)
    }

    fn rematch_schedule_from_source(
        source: &DebateSessionForRematch,
    ) -> (DateTime<Utc>, DateTime<Utc>, i32) {
        let now = Utc::now();
        let base_start = now + chrono::Duration::seconds(REMATCH_DELAY_SECS);
        let base_from = source.actual_start_at.unwrap_or(source.scheduled_start_at);
        let duration_secs = (source.end_at - base_from)
            .num_seconds()
            .clamp(REMATCH_MIN_DURATION_SECS, REMATCH_MAX_DURATION_SECS);
        let end_at = base_start + chrono::Duration::seconds(duration_secs);
        let next_round = source.rematch_round + 1;
        (base_start, end_at, next_round)
    }

    async fn ensure_rematch_session_for_vote(
        tx: &mut Transaction<'_, Postgres>,
        vote: DrawVoteRow,
    ) -> Result<DrawVoteRow, AppError> {
        let source: DebateSessionForRematch = sqlx::query_as(
            r#"
            SELECT
                id, topic_id, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, rematch_round
            FROM debate_sessions
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(vote.session_id)
        .fetch_one(&mut **tx)
        .await?;
        let (scheduled_start_at, end_at, next_round) = Self::rematch_schedule_from_source(&source);

        let existing: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM debate_sessions
            WHERE parent_session_id = $1 AND rematch_round = $2
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(source.id)
        .bind(next_round)
        .fetch_optional(&mut **tx)
        .await?;

        let rematch_session_id = if let Some((session_id,)) = existing {
            session_id
        } else {
            let insert_result: Result<(i64,), sqlx::Error> = sqlx::query_as(
                r#"
                INSERT INTO debate_sessions(
                    topic_id, status, scheduled_start_at, actual_start_at, end_at,
                    max_participants_per_side, pro_count, con_count, hot_score,
                    parent_session_id, rematch_round, created_at, updated_at
                )
                VALUES (
                    $1, 'scheduled', $2, NULL, $3,
                    $4, 0, 0, 0,
                    $5, $6, NOW(), NOW()
                )
                RETURNING id
                "#,
            )
            .bind(source.topic_id)
            .bind(scheduled_start_at)
            .bind(end_at)
            .bind(source.max_participants_per_side)
            .bind(source.id)
            .bind(next_round)
            .fetch_one(&mut **tx)
            .await;
            match insert_result {
                Ok((session_id,)) => session_id,
                Err(err) if Self::is_unique_violation(&err) => {
                    let existing_after_conflict: Option<(i64,)> = sqlx::query_as(
                        r#"
                        SELECT id
                        FROM debate_sessions
                        WHERE parent_session_id = $1 AND rematch_round = $2
                        ORDER BY created_at DESC
                        LIMIT 1
                        "#,
                    )
                    .bind(source.id)
                    .bind(next_round)
                    .fetch_optional(&mut **tx)
                    .await?;
                    if let Some((session_id,)) = existing_after_conflict {
                        session_id
                    } else {
                        return Err(err.into());
                    }
                }
                Err(err) => return Err(err.into()),
            }
        };

        if vote.rematch_session_id == Some(rematch_session_id) {
            return Ok(vote);
        }

        let updated: DrawVoteRow = sqlx::query_as(
            r#"
            UPDATE judge_draw_votes
            SET rematch_session_id = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, session_id, final_report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            "#,
        )
        .bind(vote.id)
        .bind(rematch_session_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(updated)
    }

    pub(super) async fn create_draw_vote_for_report(
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        final_report_id: i64,
    ) -> Result<(), AppError> {
        let eligible_voters: i32 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::integer
            FROM session_participants
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&mut **tx)
        .await?;
        let required_voters = calc_required_voters(eligible_voters, DRAW_VOTE_THRESHOLD_PERCENT);
        sqlx::query(
            r#"
            INSERT INTO judge_draw_votes(
                session_id, final_report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5,
                NOW() + ($6::bigint * INTERVAL '1 second'),
                'open', 'pending', NOW(), NOW()
            )
            ON CONFLICT (final_report_id) DO NOTHING
            "#,
        )
        .bind(session_id)
        .bind(final_report_id)
        .bind(DRAW_VOTE_THRESHOLD_PERCENT)
        .bind(eligible_voters)
        .bind(required_voters)
        .bind(DRAW_VOTE_WINDOW_SECS)
        .execute(&mut **tx)
        .await?;
        Ok(())
    }

    pub async fn get_draw_vote_status(
        &self,
        session_id: u64,
        user: &User,
    ) -> Result<GetDrawVoteOutput, AppError> {
        let mut tx = self.pool.begin().await?;

        let session_exists = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM debate_sessions
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if session_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let joined = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if joined.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let vote: Option<DrawVoteRow> = sqlx::query_as(
            r#"
            SELECT
                id, session_id, final_report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(vote) = vote else {
            tx.commit().await?;
            return Ok(GetDrawVoteOutput {
                session_id,
                status: "absent".to_string(),
                vote: None,
            });
        };

        let stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let mut vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &stats).await?;
        if vote.resolution == "open_rematch" {
            vote = Self::ensure_rematch_session_for_vote(&mut tx, vote).await?;
        }
        let my_vote: Option<(bool,)> = sqlx::query_as(
            r#"
            SELECT agree_draw
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(vote.id)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;

        tx.commit().await?;
        let status = vote.status.clone();
        Ok(GetDrawVoteOutput {
            session_id,
            status,
            vote: Some(map_draw_vote_detail(
                vote,
                stats,
                my_vote.map(|(agree_draw,)| agree_draw),
            )),
        })
    }

    pub async fn submit_draw_vote(
        &self,
        session_id: u64,
        user: &User,
        input: SubmitDrawVoteInput,
    ) -> Result<SubmitDrawVoteOutput, AppError> {
        let mut tx = self.pool.begin().await?;

        let session_exists = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM debate_sessions
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if session_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let joined = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if joined.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let vote: Option<DrawVoteRow> = sqlx::query_as(
            r#"
            SELECT
                id, session_id, final_report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(vote) = vote else {
            return Err(AppError::DebateConflict(format!(
                "session {} has no draw vote",
                session_id
            )));
        };

        let before_stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &before_stats).await?;
        if vote.status != "open" {
            return Err(AppError::DebateConflict(format!(
                "draw vote for session {} is already {}",
                session_id, vote.status
            )));
        }

        let existing: Option<(bool,)> = sqlx::query_as(
            r#"
            SELECT agree_draw
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(vote.id)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        let newly_submitted = existing.is_none();

        sqlx::query(
            r#"
            INSERT INTO judge_draw_vote_ballots(
                vote_id, session_id, final_report_id, user_id, agree_draw, voted_at
            )
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (vote_id, user_id)
            DO UPDATE
            SET agree_draw = EXCLUDED.agree_draw,
                voted_at = NOW()
            "#,
        )
        .bind(vote.id)
        .bind(vote.session_id)
        .bind(vote.final_report_id)
        .bind(user.id)
        .bind(input.agree_draw)
        .execute(&mut *tx)
        .await?;

        let stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let mut vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &stats).await?;
        if vote.resolution == "open_rematch" {
            vote = Self::ensure_rematch_session_for_vote(&mut tx, vote).await?;
        }

        tx.commit().await?;
        let status = vote.status.clone();
        Ok(SubmitDrawVoteOutput {
            session_id,
            status,
            vote: map_draw_vote_detail(vote, stats, Some(input.agree_draw)),
            newly_submitted,
        })
    }
}
