// Hash-based navigation: #/case/<id>/<screen>[?query], #/
export const go = (path) => {
  window.location.hash = path;
};

export function parseRoute(hash) {
  const [path] = hash.replace(/^#\/?/, "").split("?"); // screens read their own ?query (e.g. letters?l=<id>)
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "case" && parts[1]) return { name: "case", id: parts[1], screen: parts[2] || "upload" };
  return { name: "start" };
}
