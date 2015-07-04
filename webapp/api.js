// URL relative to current host, using the given protocol.
function url(path, protocol) {
  if (typeof protocol === "undefined") {
    protocol = window.location.protocol;
  }
  return protocol + "//" + window.location.host + "/" + path;
}

export const CREATE_ENDPOINT = url("api/create");
export const STATUS_ENDPOINT = url("api/status", window.location.protocol === "https:" ? "wss:" : "ws:");
export const UPLOAD_ENDPOINT = url("u");
export const DOWNLOAD_ENDPOINT = url("d");

const defaultRequestOptions = {
  "method": "GET",
  "url": "/",
  "headers": {},
  "data": null,
  "responseType": "",
};

function request(options) {
  options = Object.assign({}, defaultRequestOptions, options);

  return new Promise(function(resolve, reject) {
    var req = new XMLHttpRequest();
    req.open(options.method, options.url, true);
    req.responseType = options.responseType;

    Object.keys(options.headers || {}).forEach(function (key) {
      req.setRequestHeader(key, options.headers[key]);
    });

    req.onload = function() {
      if (req.status >= 200 && req.status < 400) {
        resolve(req.response);
      } else {
        reject(Error(`${req.status} ${req.statusText}`));
      }
    };

    req.onerror = function() {
      reject(Error("Network error"));
    };

    req.send(options.data || undefined);
  });
}

export function postJSON(url, data) {
  return request({
    "method": "POST",
    "url": url,
    "headers": {
      "Content-Type": "application/json; charset=utf-8",
    },
    "data": JSON.stringify(data),
  });
}

export function postFile(url, file) {
  return request({
    "method": "POST",
    "url": url,
    "headers": {
      "Content-Type": "application/octet-stream",
    },
    "data": file,
  });
}
