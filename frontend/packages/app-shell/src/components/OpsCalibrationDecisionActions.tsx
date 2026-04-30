import {
  type OpsJudgeRuntimeReadinessAction
} from "@echoisle/ops-domain";
import { Button, InlineHint } from "@echoisle/ui";
import type { OpsCalibrationDecisionSubmitPayload } from "./OpsCalibrationDecisionActionsModel";

type OpsCalibrationDecisionActionsProps = {
  actions: OpsJudgeRuntimeReadinessAction[];
  isPending?: boolean;
  onDecision: (payload: OpsCalibrationDecisionSubmitPayload) => void;
};

export function OpsCalibrationDecisionActions({
  actions,
  isPending = false,
  onDecision
}: OpsCalibrationDecisionActionsProps) {
  if (actions.length === 0) {
    return <InlineHint>No calibration actions.</InlineHint>;
  }

  return (
    <>
      {actions.slice(0, 2).map((action) => (
        <div className="echo-ops-rule-item" key={action.id}>
          <InlineHint>
            {action.id} | {action.severity} | {action.status || "open"}
          </InlineHint>
          <div className="echo-ops-rule-actions">
            <Button
              disabled={isPending}
              onClick={() =>
                onDecision({
                  action,
                  decision: "accept_for_review"
                })
              }
              type="button"
            >
              Accept Review
            </Button>
            <Button
              disabled={isPending}
              onClick={() =>
                onDecision({
                  action,
                  decision: "request_more_evidence"
                })
              }
              type="button"
            >
              More Evidence
            </Button>
            <Button
              disabled={isPending}
              onClick={() =>
                onDecision({
                  action,
                  decision: "defer"
                })
              }
              type="button"
            >
              Defer
            </Button>
            <Button
              disabled={isPending}
              onClick={() =>
                onDecision({
                  action,
                  decision: "reject"
                })
              }
              type="button"
            >
              Reject
            </Button>
          </div>
        </div>
      ))}
    </>
  );
}
