import { AnalyticsEventSchema } from "../gen/messages_pb";
import { create, toBinary } from "@bufbuild/protobuf";
import { ANALYTICS_API_BASE_URL } from "../judge-refresh-summary-utils";

const URL = `${ANALYTICS_API_BASE_URL}/event`;

export async function sendAppStartEvent(context, token) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "appStart",
            value: {}
        }
    });
    await sendEvent(event, token);
}

export async function sendAppExitEvent(context, token, exitCode) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "appExit",
            value: {
                exitCode,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendUserLoginEvent(context, token, payload) {
    const authFields = await buildUserAuthFields(payload);
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userLogin",
            value: authFields
        }
    });
    await sendEvent(event, token);
}

export async function sendUserLogoutEvent(context, token, payload) {
    const authFields = await buildUserAuthFields(payload);
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userLogout",
            value: authFields
        }
    });
    await sendEvent(event, token);
}

export async function sendUserRegisterEvent(context, token, payload) {
    const authFields = await buildUserAuthFields(payload);
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userRegister",
            value: authFields
        }
    });
    await sendEvent(event, token);
}

export async function sendChatCreatedEvent(context, token) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "chatCreated",
            value: {}
        }
    });
    await sendEvent(event, token);
}

export async function sendMessageSentEvent(context, token, chatId, type, size, totalFiles) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "messageSent",
            value: {
                chatId,
                type,
                size,
                totalFiles,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendChatJoinedEvent(context, token, chatId) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "chatJoined",
            value: {
                chatId,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendChatLeftEvent(context, token, chatId) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "chatLeft",
            value: {
                chatId,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendNavigationEvent(context, token, from, to) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "navigation",
            value: {
                from,
                to,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendJudgeRealtimeRefreshEvent(
    context,
    token,
    {
        debateSessionId,
        sourceEventType,
        result,
        attempts,
        retryCount,
        coalescedEvents,
        errorMessage,
    },
) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "judgeRealtimeRefresh",
            value: {
                debateSessionId: String(debateSessionId || ""),
                sourceEventType: String(sourceEventType || ""),
                result: String(result || ""),
                attempts: Number(attempts || 0),
                retryCount: Number(retryCount || 0),
                coalescedEvents: Number(coalescedEvents || 0),
                errorMessage: String(errorMessage || ""),
            },
        },
    });
    await sendEvent(event, token);
}

async function sendEvent(event, token) {
    console.log("event:", event);
    try {
        const data = toBinary(AnalyticsEventSchema, event);
        const headers = {
            "Content-Type": "application/protobuf",
        };
        // Use Authorization header to avoid token leakage in URL/query logs.
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        await fetch(URL, {
            method: "POST",
            headers,
            body: data,
            keepalive: true,
        });
    } catch (error) {
        console.error("sendEvent error:", error);
    }
}

function normalizeAuthPayload(payload) {
    if (typeof payload === "string") {
        const email = payload.trim().toLowerCase();
        return {
            accountType: email ? "email" : "unknown",
            accountIdentifier: email,
            userId: "",
            legacyEmail: email,
        };
    }
    const accountType = String(payload?.accountType || "unknown").trim().toLowerCase() || "unknown";
    const accountIdentifier = String(payload?.accountIdentifier || "").trim();
    const userId = payload?.userId == null ? "" : String(payload.userId).trim();
    const legacyEmail = accountType === "email" ? accountIdentifier.toLowerCase() : "";
    return {
        accountType,
        accountIdentifier,
        userId,
        legacyEmail,
    };
}

async function buildUserAuthFields(payload) {
    const normalized = normalizeAuthPayload(payload);
    const accountIdentifierHash = await sha1Hex(normalized.accountIdentifier);
    return {
        email: normalized.legacyEmail,
        accountType: normalized.accountType,
        accountIdentifierHash,
        userId: normalized.userId,
    };
}

async function sha1Hex(input) {
    const raw = String(input || "").trim().toLowerCase();
    if (!raw) {
        return "";
    }
    try {
        if (!globalThis?.crypto?.subtle) {
            return "";
        }
        const data = new TextEncoder().encode(raw);
        const digest = await globalThis.crypto.subtle.digest("SHA-1", data);
        const bytes = Array.from(new Uint8Array(digest));
        return bytes.map((b) => b.toString(16).padStart(2, "0")).join("");
    } catch (_err) {
        return "";
    }
}
