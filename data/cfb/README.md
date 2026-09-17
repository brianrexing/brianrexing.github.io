# College Football WhatsApp Draft Tracker

Process for turning a WhatsApp team draft into season-long standings on this GitHub Pages site.

## 1. Export the chat

1. Open the WhatsApp group where you drafted.
2. Group info → **Export chat** → **Without media**.
3. Save the `.txt` file (or email it to yourself).

WhatsApp Business Cloud API webhooks only work for *new* messages to a Business account — they cannot read a past personal group draft. An export is the right tool here.

## 2. Build `draft.csv`

**In the browser**

1. Open [cfb/import.html](../cfb/import.html).
2. Paste the export or upload the `.txt`.
3. Review picks → **Download draft.csv**.
4. Replace `data/cfb/draft.csv` with that file.

**On the command line**

```bash
python3 tools/parse_whatsapp_draft.py path/to/WhatsApp\ Chat.txt -o data/cfb/draft.csv
```

You can also edit `data/cfb/draft.csv` by hand:

```csv
pick,round,owner,team,raw_message
1,1,Brian,Ohio State,1. Ohio State
2,1,Mike,Georgia,2. Georgia
```

## 3. Refresh win-loss records

```bash
python3 tools/update_cfb_records.py --season 2026
```

This writes `data/cfb/records.csv` from ESPN. Run it weekly (or after Saturdays) and commit the updated CSV.

## 4. View the contest

- [Draft board](../cfb/draft.html)
- [Standings](../cfb/standings.html) — default **1 point per win**, 0.5 per tie

Edit scoring in `data/cfb/scoring.json`.

## Sample data

`sample_whatsapp_export.txt` and the checked-in `draft.csv` are a fake 4-person snake draft so the pages work before you import the real chat.
