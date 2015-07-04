import React from "react";

import fileSize from "./file-size.js";
import * as api from "./api.js";

let uploadsInProgress = 0;
window.onbeforeunload = () => {
  if (uploadsInProgress > 0) {
    return "An upload is in progress. Are you sure you want to exit?";
  }
  return null;
};

// Listens for events for the given upload id.
// The callback will be invoked for every incoming event.
class Subscription {
  constructor(id, callback) {
    this.id = id;
    this.callback = callback;
    this.socket = new WebSocket(`${api.STATUS_ENDPOINT}?id=${id}`);
    this.socket.onmessage = (message) => {
      this.callback(JSON.parse(message.data));
    };
    this.socket.onerror = (error) => {
      console.log("subscription websocket error", error);
      this.close();
    };
    this.socket.onclose = () => {
      console.log("subscription websocket closed");
    };
  }

  close() {
    this.socket.close();
  }
}

// Create an upload session for the given file on the server.
function createUpload(filename, file) {
  return api.postJSON(api.CREATE_ENDPOINT, {
    name: filename.trim() || file.name,
    type: file.type || "application/octet-stream",
    size: file.size,
  }).then(function (text) {
    return parseInt(text);
  });
}

// Starts the upload of the given file, connecting
// to the given upload id.
function uploadFile(uploadID, file) {
  return api.postFile(`${api.UPLOAD_ENDPOINT}/${uploadID}`, file);
}

function waitingComponent(uploadID) {
  if (uploadID === null) {
    // No ID yet.
    return (
      <p>Please wait ... </p>
    );
  }

  return (
    <div>
      Waiting for the recipent of the file.
      Please give the following link to your partner:
      <div className="download-link">
        {`${api.DOWNLOAD_ENDPOINT}/${uploadID}`}
      </div>
    </div>
  );
}

function errorComponent(message) {
  return (
    <div className="alert alert-danger">
      <strong>Error. </strong>
      {message}
    </div>
  );
}

// "status" is "running", "done" or "error".
function progressComponent(done, size, status) {
  const progress = Math.round((done / size) * 10000) / 100;
  const progressType = status === "error" ? "progress-bar-danger" : "progress-bar-success";

  const doneText = fileSize(done);
  const sizeText = fileSize(size);
  let statusText;
  if (status === "error") {
    statusText = "Failed.";
  } else if (status === "done") {
    statusText = `Done (${sizeText}).`;
  } else if (status === "running") {
    statusText = `${doneText} of ${sizeText}.`;
  }

  return (
    <div>
      <div className="progress">
        <div
          className={`progress-bar ${progressType}`}
          style={{width: `${progress}%`}}>
        </div>
      </div>
      <p className="text-center">
        {statusText}
      </p>
    </div>
  );
}

function buttonComponent(text, classes, handler) {
  return (
    <button className={classes} onClick={handler}>
      {text}
    </button>
  );
}

let UploadStatus = React.createClass({
  getInitialState() {
    return {
      id: null,
      status: "waiting", // "waiting", "running", "done", "error",
      bytesTransferred: 0, // for status "running" and "done",
      errorMessage: null, // for status "error"
    };
  },

  componentWillMount() {
    createUpload(this.props.filename, this.props.file)
      .then(uploadID => {
        this.setState({
          id: uploadID,
        });
        this.sub = new Subscription(this.state.id, this.onUploadEvent);
        uploadFile(this.state.id, this.props.file)
          .catch(error => {
            this.setError("Failed to upload file.");
            console.log("Failed to upload file", error);
          });
      })
      .catch(error => {
        this.setError("Failed to create upload session.");
        console.log("Failed to create upload session", error);
      });
  },

  componentWillUnmount() {
    if (this.sub) {
      this.sub.close();
      this.sub = null;
    }
  },

  render() {
    const id = this.state.id;
    const status = this.state.status;
    const transferred = this.state.bytesTransferred;
    const size = this.props.file.size;

    const error = status === "error"
                    ? errorComponent(this.state.errorMessage)
                    : null;
    const progress = status === "waiting"
                      ? waitingComponent(id)
                      : progressComponent(transferred, size, status);

    const button = (status === "done" || status === "error")
                    ? buttonComponent("New Transfer", "btn btn-success", this.onCreateNewClick)
                    : buttonComponent("Cancel", "btn btn-default", this.onCancelClick);
    return (
      <div className="upload-status">
        <h3>Transfer Status</h3>
        {error}
        {progress}
        <div className="buttons">
          {button}
        </div>
      </div>
    );
  },

  setError(message) {
    this.unregisterUpload();
    // Only the first error will be shown.
    if (this.state.status !== "error") {
      this.setState({
        status: "error",
        errorMessage: message,
      });
    }
  },

  onCancelClick(event) {
    event.preventDefault();

    if (this.sub) {
      this.sub.close();
      this.sub = null;
    }
    if (this.props.onCancel) {
      this.props.onCancel();
    }
  },

  onCreateNewClick(event) {
    event.preventDefault();

    if (this.props.onNew) {
      this.props.onNew();
    }
  },

  onUploadEvent(event) {
    console.log("event", event);
    switch (event.type) {
      case "start":
        this.registerUpload();
        this.setState({
          status: "running",
          bytesTransferred: 0,
        });
        break;
      case "progress":
        this.setState({
          status: "running",
          bytesTransferred: event.done,
        });
        break;
      case "done":
        this.unregisterUpload();
        this.setState({
          status: "done",
          bytesTransferred: this.props.file.size,
        });
        break;
      case "error":
        this.setError("File transfer failed.");
        break;
      case "timeout":
        this.setError("The receiver did not connect in time.");
        break;
      default:
        console.log("invalid event type", event.type);
        break;
    }
  },

  registerUpload() {
    if (this.uploadRegistered) {
      return;
    }
    this.uploadRegistered = true;
    uploadsInProgress++;
  },

  unregisterUpload() {
    if (!this.uploadRegistered) {
      return;
    }
    this.uploadRegistered = false;
    uploadsInProgress--;
  },
});

export default UploadStatus;
