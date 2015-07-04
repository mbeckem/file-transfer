import React from "react";

function error(message) {
  if (!message) { return null; }
  return (
    <div className="alert alert-danger">
      <strong>Error.</strong> {message}
    </div>
  );
}

function form(onSubmit) {
  return (
    <form ref="form" className="form-horizontal" onSubmit={onSubmit}>
      <div className="form-group">
        <label htmlFor="form-name" className="col-sm-4 control-label">Filename</label>
        <div className="col-sm-8">
          <input ref="filename" id="form-name" type="text" className="form-control" placeholder="Optional" />
        </div>
      </div>
      <div className="form-group">
        <label htmlFor="form-file" className="col-sm-4 control-label">File</label>
        <div className="col-sm-8">
          <input ref="file" id="form-file" type="file" />
        </div>
      </div>
      <div className="form-group">
        <div className="col-sm-offset-4 col-sm-8">
          <button type="submit" className="btn btn-success">Start Transfer</button>
        </div>
      </div>
    </form>
  );
}

const UploadForm = React.createClass({
  getInitialState() {
    return {
      error: null,
    };
  },

  render() {
    return (
      <div>
        <h3>Create New Transfer</h3>
        {error(this.state.error)}
        {form(this.handleSubmit)}
      </div>
    );
  },

  handleSubmit(e) {
    e.preventDefault();

    let files = React.findDOMNode(this.refs.file).files;
    if (files.length === 0) {
      this.setState({
        error: "Please select a file.",
      });
      return;
    }

    let filename = React.findDOMNode(this.refs.filename).value.trim();
    let file = files[0];
    if (this.props.onSubmit) {
      this.props.onSubmit(filename, file);
    }

    this.setState({
      error: null,
    });
  },
});

export default UploadForm;
