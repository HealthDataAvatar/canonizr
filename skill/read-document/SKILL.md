---
name: read-document
description: Convert any document to markdown using Canonizr
---

Read any document using the Canonizr pipeline. Supports PDFs, images, office files, and more.

## Using Canonizr

Convert a document to markdown:

```sh
canonizr convert document.pdf
```

This writes the markdown to `document.pdf.md` and prints a job summary (JSON) to stdout. If the output file already exists, the conversion is skipped — so it's safe to run repeatedly.

To overwrite an existing output:

```sh
canonizr convert document.pdf -f
```

To get the markdown directly to stdout (for piping):

```sh
canonizr convert document.pdf -o -
```

The job JSON includes a `completeness` field (`"full"` or `"partial"`) and a `warnings` array describing any issues (e.g. images that could not be captioned).

## Debugging

Check if the Canonizr pipeline is running:

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
