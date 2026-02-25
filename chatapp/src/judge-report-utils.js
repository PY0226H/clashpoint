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

export function isDrawVoteOpen(vote) {
  return String(vote?.status || '') === 'open';
}

export function drawVoteResolutionText(resolution) {
  switch (String(resolution || '')) {
    case 'accept_draw':
      return '用户同意平局，不开启二番战';
    case 'open_rematch':
      return '用户不同意平局，将开启二番战';
    default:
      return '暂无决议';
  }
}

export function drawVoteChoiceText(agreeDraw) {
  if (agreeDraw === true) {
    return '已投：同意平局';
  }
  if (agreeDraw === false) {
    return '已投：不同意平局';
  }
  return '你还未投票';
}
