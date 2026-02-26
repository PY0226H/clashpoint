export function pickDefaultPeerUserId(usersMap = {}, selfUserId = null) {
  const selfId = Number(selfUserId);
  if (!Number.isFinite(selfId)) {
    return null;
  }

  const users = Object.values(usersMap || {});
  const peer = users.find((user) => Number(user?.id) !== selfId);
  if (!peer) {
    return null;
  }
  const peerId = Number(peer.id);
  return Number.isFinite(peerId) ? peerId : null;
}

export function pickActiveChannelId(channels = [], preferredId = null) {
  if (!Array.isArray(channels) || channels.length === 0) {
    return null;
  }

  const preferred = Number(preferredId);
  if (Number.isFinite(preferred)) {
    const found = channels.find((channel) => Number(channel?.id) === preferred);
    if (found) {
      return Number(found.id);
    }
  }

  const first = Number(channels[0]?.id);
  return Number.isFinite(first) ? first : null;
}

