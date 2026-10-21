# Third-party code

## JsonParser.pas

- Source: <https://github.com/koldev/JsonParser> (file `JsonParser.pas`, branch `master`, downloaded on October 17, 2026).
- License: public domain. The upstream README says: "This code is in the Public Domain. NO WARRANTY EXPRESSED OR IMPLIED. USE AT YOUR OWN RISK."
- SHA-256 of the upstream file: `60ce760a2f48e046e3405bc4b3467449f2434545ddfcd4c6fbe00ff476ae111b`.

Local change: the `Error` procedure now sets the parser to the end of the text. The upstream parser does not stop after a syntax error. A malformed text, such as a missing `}`, makes it repeat the same error without end. The installer must never hang on a broken manifest, so parsing stops at the first error.
