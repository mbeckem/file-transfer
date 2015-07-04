import React from "react";

import UploadForm from "./upload-form.jsx";
import UploadStatus from "./upload-status.jsx";

let Application = React.createClass({
  componentWillMount() {
    this.onUploadCreate();
  },

  render() {
    return this.state.element;
  },

  onUploadSubmit(filename, file) {
    this.setState({
      element: (
        <UploadStatus
          filename={filename} file={file}
          onNew={this.onUploadCreate} onCancel={this.onUploadCreate}
        />
      ),
    });
  },

  onUploadCreate() {
    this.setState({
      element: (<UploadForm onSubmit={this.onUploadSubmit} />),
    });
  },
});

export default Application;
