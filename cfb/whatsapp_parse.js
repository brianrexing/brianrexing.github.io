/* Browser port of tools/parse_whatsapp_draft.py */
window.WhatsAppDraft = (function () {
  const WA_BRACKET = /^\[([^\]]+)\]\s+([^:]+):\s+(.*)$/;
  const WA_DASH =
    /^(\d{1,2}\/\d{1,2}\/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s+(.*)$/i;
  const SIMPLE = /^([^:]+):\s+(.+)$/;

  const PICK_PATTERNS = [
    /^(?:pick\s*)?(?:#\s*)?(\d{1,3})[.):\-\s]+(.+)$/i,
    /^(?:round|r)\s*(\d{1,2})\s*[-:)\s]+(.+)$/i,
    /^(?:i\s+)?(?:take|taking|drafting|select(?:ing)?|grab(?:bing)?)\s+(.+)$/i,
  ];
  const BARE_TEAM = /^([A-Za-z0-9 .&'\-]{3,40})$/;
  const SKIP_BODY =
    /^(ok|okay|lol|lmao|haha|yes|no|yep|nah|thanks|thank you|nice|damn|ready|fire away|let'?s do this|let'?s go|good luck.*|draft locked.*|<media omitted>|image omitted|video omitted|sticker omitted|this message was deleted|you deleted this message|messages and calls are end-to-end encrypted).*$/i;

  function normalize(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[^a-z0-9& ]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanTeam(raw) {
    let team = String(raw || "")
      .trim()
      .replace(/^["'`*]+|["'`*]+$/g, "");
    team = team.replace(/\s+/g, " ").replace(/[.!?]+$/, "");
    [" - ", " — ", " (", "!"].forEach((sep) => {
      if (team.includes(sep)) team = team.split(sep)[0].trim();
    });
    return team;
  }

  function matchKnownTeam(raw, knownTeams) {
    if (!knownTeams || !knownTeams.length) return raw;
    const needle = normalize(raw);
    if (!needle) return null;

    const exact = knownTeams.find((t) => normalize(t) === needle);
    if (exact) return exact;

    let best = null;
    let bestScore = 0;
    knownTeams.forEach((candidate) => {
      const cand = normalize(candidate);
      if (!cand) return;
      if (needle.includes(cand) || cand.includes(needle)) {
        const score = Math.min(needle.length, cand.length);
        if (score > bestScore) {
          best = candidate;
          bestScore = score;
        }
      }
    });
    if (best && bestScore >= Math.min(4, needle.length)) return best;
    return null;
  }

  function parseBody(body, knownTeams) {
    body = String(body || "").trim();
    if (!body || SKIP_BODY.test(body)) return null;

    for (let i = 0; i < PICK_PATTERNS.length; i++) {
      const match = body.match(PICK_PATTERNS[i]);
      if (!match) continue;
      let pick = null;
      let round = null;
      let teamRaw = "";
      if (i === 0) {
        pick = Number(match[1]);
        teamRaw = match[2];
      } else if (i === 1) {
        round = Number(match[1]);
        teamRaw = match[2];
      } else {
        teamRaw = match[1];
      }
      const team = cleanTeam(teamRaw);
      if (team.length < 2 || team.split(/\s+/).length > 6) continue;
      const resolved = knownTeams.length
        ? matchKnownTeam(team, knownTeams)
        : team;
      if (knownTeams.length && !resolved) continue;
      return { team: resolved || team, pick, round };
    }

    const bare = body.match(BARE_TEAM);
    if (bare && knownTeams.length) {
      const resolved = matchKnownTeam(cleanTeam(bare[1]), knownTeams);
      if (resolved) return { team: resolved, pick: null, round: null };
    }
    return null;
  }

  function iterMessages(text) {
    const messages = [];
    let currentSender = null;
    let currentBody = [];

    function flush() {
      if (currentSender != null) {
        messages.push({
          sender: currentSender.trim(),
          body: currentBody.join("\n").trim(),
        });
      }
      currentSender = null;
      currentBody = [];
    }

    String(text || "")
      .replace(/^\ufeff/, "")
      .split(/\n/)
      .forEach((rawLine) => {
        const line = rawLine.replace(/\r$/, "");
        if (!line.trim()) return;

        let matched = null;
        let sender = "";
        let body = "";

        let m = line.match(WA_BRACKET);
        if (m) {
          matched = true;
          sender = m[2];
          body = m[3];
        } else {
          m = line.match(WA_DASH);
          if (m) {
            matched = true;
            sender = m[2];
            body = m[3];
          } else {
            m = line.match(SIMPLE);
            if (m && !m[1].includes("/")) {
              matched = true;
              sender = m[1];
              body = m[2];
            }
          }
        }

        if (matched) {
          flush();
          currentSender = sender;
          currentBody = [body];
        } else if (currentSender != null) {
          currentBody.push(line);
        }
      });

    flush();
    return messages;
  }

  function extractPicks(text, knownTeams) {
    knownTeams = knownTeams || [];
    const picks = [];
    let autoPick = 1;

    iterMessages(text).forEach(({ sender, body }) => {
      const lower = body.toLowerCase();
      if (lower.includes("created group") || lower.includes("added you")) return;
      const parsed = parseBody(body, knownTeams);
      if (!parsed) return;
      const pickNum = parsed.pick == null ? autoPick : parsed.pick;
      picks.push({
        pick: pickNum,
        round: parsed.round || "",
        owner: sender,
        team: parsed.team,
        raw_message: body,
      });
      autoPick = Math.max(autoPick, pickNum) + 1;
    });

    const uniquePickNums = new Set(picks.map((p) => p.pick));
    if (uniquePickNums.size !== picks.length) {
      picks.forEach((p, idx) => {
        p.pick = idx + 1;
      });
    }

    const owners = [...new Set(picks.map((p) => p.owner))];
    if (owners.length && picks.every((p) => p.round === "")) {
      picks.forEach((p) => {
        p.round = Math.floor((p.pick - 1) / owners.length) + 1;
      });
    }

    const seen = new Set();
    return picks.filter((p) => {
      const key = `${p.owner.toLowerCase()}::${p.team.toLowerCase()}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  return { extractPicks };
})();
