---
name: read-document
description: Convert any document to markdown using Canonizr
---

Read any document using the Canonizr pipeline. Supports PDFs, images, office files, and more.

## Using Canonizr

You can pass documents to Canonizr via CLI.

```sh
canonizr convert document.pdf
```

The output of the above command is a direct markdown transcript.

Failed attempts to convert a file return an error message. Depending on context you may wish to store the output in an adjacent `.md` file to avoid re-processing.

Supported file formats include PDFs, images (which will be transcribed), and office files.

## Debugging

You can check if the Canonizr pipeline is running by using the CLI:

```sh
canonizr health
```

If the pipeline is not running then your user may not have started it. If you have docker permissions then you can start the service with:

```sh
canonizr up
```

And stop it with:

```sh
canonizr down
```

You can get a full JSON response with metadata (instead of just markdown) using the `--json` flag:

```sh
canonizr convert --json document.pdf
```