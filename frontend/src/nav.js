// Hash-based navigation: #/case/<id>/<screen>, #/share/<token>, #/
export const go = (path) => {
  window.location.hash = path;
};
