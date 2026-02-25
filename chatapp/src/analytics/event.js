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

export async function sendUserLoginEvent(context, token, email) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userLogin",
            value: {
                email,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendUserLogoutEvent(context, token, email) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userLogout",
            value: {
                email,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendUserRegisterEvent(context, token, email, workspaceId) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "userRegister",
            value: {
                email,
                workspaceId,
            }
        }
    });
    await sendEvent(event, token);
}

export async function sendChatCreatedEvent(context, token, workspaceId) {
    const event = create(AnalyticsEventSchema, {
        context,
        eventType: {
            case: "chatCreated",
            value: {
                workspaceId,
            }
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
