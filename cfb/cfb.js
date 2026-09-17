/* Shared helpers for CFB draft pages */
window.Cfb = (function () {
  function parseCsv(text) {
    const rows = [];
    let row = [];
    let cell = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      const next = text[i + 1];
      if (inQuotes) {
        if (ch === '"' && next === '"') {
          cell += '"';
          i++;
        } else if (ch === '"') {
          inQuotes = false;
        } else {
          cell += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        row.push(cell);
        cell = "";
      } else if (ch === "\n") {
        row.push(cell);
        rows.push(row);
        row = [];
        cell = "";
      } else if (ch === "\r") {
        // ignore
      } else {
        cell += ch;
      }
    }
    if (cell.length || row.length) {
      row.push(cell);
      rows.push(row);
    }
    if (!rows.length) return [];
    const headers = rows[0].map((h) => h.trim());
    return rows
      .slice(1)
      .filter((r) => r.some((c) => String(c).trim() !== ""))
      .map((r) => {
        const obj = {};
        headers.forEach((h, idx) => {
          obj[h] = (r[idx] || "").trim();
        });
        return obj;
      });
  }

  async function loadCsv(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Could not load ${path}`);
    return parseCsv(await res.text());
  }

  function normalize(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[^a-z0-9& ]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildTeamIndex(records) {
    const index = [];
    records.forEach((rec) => {
      ["team", "display_name", "location", "abbreviation", "nickname"].forEach((key) => {
        const value = rec[key];
        if (value) index.push({ key: normalize(value), rec });
      });
      if (rec.location && rec.nickname) {
        index.push({
          key: normalize(`${rec.location} ${rec.nickname}`),
          rec,
        });
      }
    });
    return index;
  }

  function matchTeam(name, index) {
    const needle = normalize(name);
    if (!needle) return null;
    const exact = index.find((item) => item.key === needle);
    if (exact) return exact.rec;

    let best = null;
    let bestScore = 0;
    index.forEach((item) => {
      if (item.key.includes(needle) || needle.includes(item.key)) {
        const score = Math.min(item.key.length, needle.length);
        if (score > bestScore) {
          best = item.rec;
          bestScore = score;
        }
      }
    });
    return bestScore >= Math.min(4, needle.length) ? best : null;
  }

  function scorePick(rec, scoring) {
    if (!rec) return { points: 0, wins: 0, losses: 0, ties: 0, record: "—" };
    const wins = Number(rec.wins || 0);
    const losses = Number(rec.losses || 0);
    const ties = Number(rec.ties || 0);
    const points =
      wins * (scoring.points_per_win || 1) + ties * (scoring.points_per_tie || 0.5);
    return {
      points,
      wins,
      losses,
      ties,
      record: rec.record || `${wins}-${losses}`,
    };
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function toDraftCsv(picks) {
    const header = "pick,round,owner,team,raw_message";
    const lines = picks.map((p) => {
      const raw = String(p.raw_message || "").replace(/"/g, '""');
      const team = String(p.team || "").replace(/"/g, '""');
      const owner = String(p.owner || "").replace(/"/g, '""');
      return `${p.pick},${p.round},"${owner}","${team}","${raw}"`;
    });
    return [header, ...lines].join("\n") + "\n";
  }

  return {
    parseCsv,
    loadCsv,
    normalize,
    buildTeamIndex,
    matchTeam,
    scorePick,
    downloadText,
    toDraftCsv,
  };
})();
