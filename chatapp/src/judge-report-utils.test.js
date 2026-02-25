import assert from 'node:assert/strict';
import { mergeJudgeReportWindow, normalizeSessionId } from './judge-report-utils.js';

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
