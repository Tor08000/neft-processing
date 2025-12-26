# Client Portal · Documents

## Routes

- `/client/documents` — document list
- `/client/documents/{id}` — document details

## List view

Filters:

- period (from / to)
- document type
- status (`ISSUED/ACKNOWLEDGED/FINALIZED/VOID`)
- signed / awaiting

Table columns:

- Type
- Period
- Number
- Status
- Date
- Actions

Client actions:

| Action | Availability |
| --- | --- |
| Download | `ISSUED+` |
| Acknowledge | `ISSUED` |
| Sign | `ISSUED` / `ACKNOWLEDGED` |
| View history | Always |

Restrictions:

- Client cannot edit, delete, or regenerate documents.

## Document details

Displayed data:

- metadata (type, period, number, version)
- status
- file list (PDF/XLSX)
- document hash (read-only)
- event history
- legal wording for acknowledgement
