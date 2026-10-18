// Thin wrapper over the Virasat API. Errors carry the server's plain-language `detail`.

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("We couldn't reach Virasat. Please check your internet connection.");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

const c = (id) => `/api/cases/${id}`;

export const api = {
  createCase: (body) => request("POST", "/api/cases", body),
  getCase: (id) => request("GET", c(id)),
  patchCase: (id, body) => request("PATCH", c(id), body),
  deleteCase: (id) => request("DELETE", c(id)),
  leaveCase: (id) => request("POST", `${c(id)}/leave`),
  upload: (id, files) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return request("POST", `${c(id)}/documents`, form);
  },
  removeDocument: (id, docId) => request("DELETE", `${c(id)}/documents/${docId}`),
  unlock: (id, docId, password) => request("POST", `${c(id)}/documents/${docId}/unlock`, { password }),
  extract: (id, docId) => request("POST", `${c(id)}/documents/${docId}/extract`),
  analyse: (id) => request("POST", `${c(id)}/analyse`),
  setItemStatus: (id, itemId, status) => request("POST", `${c(id)}/items/${itemId}/status`, { status }),
  generateQuestions: (id) => request("POST", `${c(id)}/questions/generate`),
  answer: (id, qid, answer) => request("POST", `${c(id)}/questions/${qid}/answer`, { answer }),
  buildPlan: (id) => request("POST", `${c(id)}/plan`),
  setTask: (id, taskId, board_status) => request("PATCH", `${c(id)}/plan/tasks/${taskId}`, { board_status }),
  createLetter: (id, item_id) => request("POST", `${c(id)}/letters`, { item_id }),
  editLetter: (id, letterId, title, body) => request("PUT", `${c(id)}/letters/${letterId}`, { title, body }),
  letterPdfUrl: (id, letterId) => `${c(id)}/letters/${letterId}/pdf`,
  addMemory: (id, { audio, text }) => {
    const form = new FormData();
    if (audio) form.append("audio", audio, "memory.wav");
    else form.append("text", text);
    return request("POST", `${c(id)}/memories`, form);
  },
  checkNames: (id) => request("POST", `${c(id)}/name-check`),
  addReply: (id, taskId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request("POST", `${c(id)}/plan/tasks/${taskId}/replies`, form);
  },
  setRequirement: (id, replyId, reqId, done) =>
    request("PATCH", `${c(id)}/replies/${replyId}/requirements/${reqId}`, { done }),
  sampleUrl: (name) => `/api/demo/samples/${name}`,
  sampleFile: async (name) => {
    const response = await fetch(`/api/demo/samples/${name}`);
    if (!response.ok) throw new Error("The sample file couldn't be loaded.");
    const blob = await response.blob();
    return new File([blob], name, { type: blob.type });
  },
};
