export class ApiError extends Error {
  constructor(message, { code = "client_error", status = 0, requestId = "", details = {}, cause } = {}) {
    super(message, { cause });
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.details = details;
  }
}

function statusCode(status) {
  if (status === 400) return "validation_error";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status >= 500) return "server_error";
  return "http_error";
}

export async function request(path, { method = "GET", body, signal, timeout = 10000 } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);
  const relayAbort = () => controller.abort();
  signal?.addEventListener("abort", relayAbort, { once: true });

  const headers = { Accept: "application/json" };
  const options = { method, headers, signal: controller.signal };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(path, options);
    const requestId = response.headers.get("X-Request-ID") || "";
    const contentType = response.headers.get("Content-Type") || "";
    if (!contentType.includes("application/json")) {
      throw new ApiError("服务返回了无法识别的响应。", {
        code: "invalid_response",
        status: response.status,
        requestId,
      });
    }

    let payload;
    try {
      payload = await response.json();
    } catch (cause) {
      throw new ApiError("服务返回的内容不是有效 JSON。", {
        code: "invalid_json",
        status: response.status,
        requestId,
        cause,
      });
    }

    if (!payload || typeof payload !== "object" || typeof payload.success !== "boolean") {
      throw new ApiError("服务响应缺少必要字段。", {
        code: "invalid_contract",
        status: response.status,
        requestId,
      });
    }

    if (!response.ok || !payload.success) {
      const error = payload.error && typeof payload.error === "object" ? payload.error : {};
      throw new ApiError(error.message || "请求未能完成。", {
        code: error.code || statusCode(response.status),
        status: response.status,
        requestId,
        details: error.details || {},
      });
    }
    if (!("data" in payload)) {
      throw new ApiError("服务响应缺少数据字段。", {
        code: "invalid_contract",
        status: response.status,
        requestId,
      });
    }
    return payload.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") {
      throw new ApiError(timedOut ? "读取超时，请稍后重试。" : "请求已取消。", {
        code: timedOut ? "timeout" : "cancelled",
        cause: error,
      });
    }
    throw new ApiError("无法连接本机 Life OS 服务。", {
      code: "connection_error",
      cause: error,
    });
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", relayAbort);
  }
}

export const api = {
  get(path, options = {}) {
    return request(path, { ...options, method: "GET" });
  },
  post(path, body, options = {}) {
    return request(path, { ...options, method: "POST", body });
  },
  put(path, body, options = {}) {
    return request(path, { ...options, method: "PUT", body });
  },
  delete(path, options = {}) {
    return request(path, { ...options, method: "DELETE" });
  },
};
