import assert from 'node:assert/strict';
import {
  drawVoteChoiceText,
  drawVoteDecisionSourceText,
  drawVoteResolutionText,
  isDrawVoteOpen,
  mergeJudgeReportWindow,
  normalizeSessionId,
} from './judge-report-utils';

const currentPayload = {
  report: {
    stageSummaries: [
      { stageNo: 1, fromMessageId: 1, toMessageId: 100, createdAt: '2026-02-24T00:00:00Z' },
    ],
    stageSummariesMeta: {
      totalCount: 3,
      returnedCount: 1,
      stageOffset: 0,
      hasMore: true,
      nextOffset: 1,
      truncated: true,
      maxStageCount: 1,
    },
  },
};

const nextPayload = {
  report: {
    stageSummaries: [
      { stageNo: 2, fromMessageId: 101, toMessageId: 200, createdAt: '2026-02-24T00:01:00Z' },
    ],
    stageSummariesMeta: {
      totalCount: 3,
      returnedCount: 1,
      stageOffset: 1,
      hasMore: true,
      nextOffset: 2,
      truncated: true,
      maxStageCount: 1,
    },
  },
};

const merged = mergeJudgeReportWindow(currentPayload, nextPayload);
assert.equal(merged.report.stageSummaries.length, 2);
assert.equal(merged.report.stageSummaries[0].stageNo, 1);
assert.equal(merged.report.stageSummaries[1].stageNo, 2);
assert.equal(merged.report.stageSummariesMeta.stageOffset, 1);

assert.equal(normalizeSessionId('12'), 12);
assert.equal(normalizeSessionId(' 7 '), 7);
assert.equal(normalizeSessionId('0'), null);
assert.equal(normalizeSessionId('-1'), null);
assert.equal(normalizeSessionId('abc'), null);

assert.equal(isDrawVoteOpen({ status: 'open' }), true);
assert.equal(isDrawVoteOpen({ status: 'decided' }), false);
assert.equal(drawVoteResolutionText('accept_draw'), '用户同意平局，不开启二番战');
assert.equal(drawVoteResolutionText('open_rematch'), '用户不同意平局，将开启二番战');
assert.equal(drawVoteResolutionText(''), '暂无决议');
assert.equal(drawVoteDecisionSourceText('threshold_reached'), '达到投票门槛后完成判定');
assert.equal(drawVoteDecisionSourceText('vote_timeout'), '投票超时后完成判定');
assert.equal(drawVoteDecisionSourceText(''), '投票进行中，尚未完成判定');
assert.equal(drawVoteChoiceText(true), '已投：同意平局');
assert.equal(drawVoteChoiceText(false), '已投：不同意平局');
assert.equal(drawVoteChoiceText(undefined), '你还未投票');
