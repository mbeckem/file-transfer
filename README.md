File-Transfer Utility
=====================

A simple Python based web service for exchanging files.
Transferring files works like this:

* The user creates an upload session on the website and receives a one-time link.
* The receiver of the file uses the one-time-link to accept the file.
* The file is copied on the fly between the two clients.

Requirements
------------

* Python dependencies: see `requirements.txt`.
* Nodejs and npm, then use `make deps`.

`make` produces a compiled version of the web application in the `dist` directory.
After entering the `dist` directory, launch the server by executing `./run dev` or `./run prod`.

Screenshots
-----------

![Upload session creation](https://raw.githubusercontent.com/mbeckem/file-transfer/master/screen1.png)
![Generated download link](https://raw.githubusercontent.com/mbeckem/file-transfer/master/screen2.png)
![Transfer in progress](https://raw.githubusercontent.com/mbeckem/file-transfer/master/screen3.png)
![Transfer completed](https://raw.githubusercontent.com/mbeckem/file-transfer/master/screen4.png)

License
-------

MIT, see `LICENCE` file.
