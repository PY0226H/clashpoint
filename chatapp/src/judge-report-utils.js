function stageKey(stage) {
  const stageNo = stage?.stageNo ?? '';
  const from = stage?.fromMessageId ?? '';
  const to = stage?.toMessageId ?? '';
  return `${stageNo}:${from}:${to}`;
}

export function mergeJudgeReportWindow(currentPayload, nextPayload) {
  if (!currentPayload?.report || !nextPayload?.report) {
    return nextPayload;
  }
  const currentStages = currentPayload.report.stageSummaries || [];
  const nextStages = nextPayload.report.stageSummaries || [];
  const mergedStages = [];
  const seen = new Set();

  for (const item of [...currentStages, ...nextStages]) {
    const key = stageKey(item);
    if (!seen.has(key)) {
      seen.add(key);
      mergedStages.push(item);
    }
  }

  mergedStages.sort((a, b) => {
    const stageNoA = Number(a?.stageNo || 0);
    const stageNoB = Number(b?.stageNo || 0);
    if (stageNoA !== stageNoB) {
      return stageNoA - stageNoB;
    }
    return String(a?.createdAt || '').localeCompare(String(b?.createdAt || ''));
  });

  return {
    ...nextPayload,
    report: {
      ...nextPayload.report,
      stageSummaries: mergedStages,
    },
  };
}

export function normalizeSessionId(input) {
  const n = Number(String(input || '').trim());
  if (!Number.isInteger(n) || n <= 0) {
    return null;
  }
  return n;
}
