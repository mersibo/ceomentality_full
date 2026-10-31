# T-Bank TLS certificates

The T-Bank HTTP client loads these public CA certificates into a dedicated TLS
context. Other outbound integrations continue to use the standard system trust
store.

Official source: https://www.gosuslugi.ru/crt

- `russian_trusted_root_ca.crt`
  - Subject: `CN=Russian Trusted Root CA`
  - Certificate SHA-256 fingerprint:
    `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31`
- `russian_trusted_sub_ca.crt`
  - Subject: `CN=Russian Trusted Sub CA`
  - Certificate SHA-256 fingerprint:
    `BB:BD:E2:10:3E:79:0B:99:9E:C6:2B:D0:3C:F6:25:A5:A2:E7:C3:16:E1:0A:FE:6A:49:0E:ED:EA:D8:B3:FD:9B`

Never replace these files without checking the certificate subject, issuer,
validity period, and SHA-256 fingerprint against an independent official source.
