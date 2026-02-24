# app.py
import streamlit as st
import random
import math
import difflib
import graphviz

st.set_page_config(page_title="Dynamic Tournament Generator", page_icon="🎲", layout="centered")
st.title("Dynamic Tournament Generator 🎲")

# =========================================================
# ---------------------- Entrants -------------------------
# =========================================================
st.header("Entrants")
entrants = st.text_area("Enter player names (one per line):", height=200)
players = [p.strip() for p in entrants.splitlines() if p.strip()]

# =========================================================
# ------------------- Session State -----------------------
# =========================================================
if "round" not in st.session_state:
    st.session_state.round = 1
if "matches" not in st.session_state:
    st.session_state.matches = []
if "winners" not in st.session_state:
    st.session_state.winners = []
if "history" not in st.session_state:
    st.session_state.history = []  # list of (round_number, [(p1, p2, winner), ...])
if "initial_players" not in st.session_state:
    st.session_state.initial_players = []
if "round_generated" not in st.session_state:
    st.session_state.round_generated = False
if "byes" not in st.session_state:
    st.session_state.byes = []

# Near-duplicate review state
if "dupe_pairs" not in st.session_state:
    st.session_state.dupe_pairs = []
if "dupe_threshold" not in st.session_state:
    st.session_state.dupe_threshold = 0.92
if "dupe_scan_done" not in st.session_state:
    st.session_state.dupe_scan_done = False
if "dupe_decisions" not in st.session_state:
    st.session_state.dupe_decisions = {}
if "cleaned_players" not in st.session_state:
    st.session_state.cleaned_players = None
if "auto_disambiguate" not in st.session_state:
    # Ensures identical names become unique labels, which keeps Graphviz happy
    st.session_state.auto_disambiguate = True

# =========================================================
# ---------------------- Utilities ------------------------
# =========================================================
def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))

def disambiguate_duplicates(names):
    """
    If a name appears multiple times (case-insensitive), suffix subsequent
    occurrences with (2), (3), etc. Preserves order.
    """
    seen = {}
    out = []
    for n in names:
        key = n.lower().strip()
        count = seen.get(key, 0) + 1
        seen[key] = count
        if count == 1:
            out.append(n)
        else:
            out.append(f"{n} ({count})")
    return out

def find_near_dupes(names, threshold=0.92):
    """
    Returns a list of dicts (sorted by similarity desc):
    {
      'i': index of first name,
      'j': index of second name,
      'a': first name (original),
      'b': second name (original),
      'score': similarity ratio in [0,1]
    }
    Flags near-duplicates (non-identical) above threshold,
    and also flags exact duplicates (case-insensitive) with score=1.0.
    """
    pairs = []
    cleaned = [n.strip() for n in names]

    # Near-duplicates (not exact equal when case-insensitive)
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            a, b = cleaned[i], cleaned[j]
            la, lb = a.lower(), b.lower()
            if la != lb:
                score = difflib.SequenceMatcher(None, la, lb).ratio()
                if score >= threshold:
                    pairs.append({"i": i, "j": j, "a": a, "b": b, "score": score})

    # Exact duplicates (case-insensitive), scored as 1.0
    index_by_key = {}
    for idx, name in enumerate(cleaned):
        key = name.lower()
        index_by_key.setdefault(key, []).append(idx)
    for indices in index_by_key.values():
        if len(indices) > 1:
            for x in range(len(indices) - 1):
                i, j = indices[x], indices[x + 1]
                a, b = cleaned[i], cleaned[j]
                pairs.append({"i": i, "j": j, "a": a, "b": b, "score": 1.0})

    # Sort most similar first
    pairs.sort(key=lambda d: d["score"], reverse=True)
    return pairs

# =========================================================
# ------------- Near‑duplicate Review (Optional) ----------
# =========================================================
st.subheader("Near‑duplicate names (optional review)")
st.caption(
    "Use this to flag and review similar names (e.g., family members with similar names). "
    "You decide whether to keep both or remove one."
)

st.session_state.auto_disambiguate = st.checkbox(
    "Auto‑disambiguate identical names by adding (2), (3), etc. (recommended)",
    value=st.session_state.auto_disambiguate,
    help="This ensures identical names remain separate in fixtures and in the bracket."
)

st.session_state.dupe_threshold = st.slider(
    "Similarity threshold (higher = stricter)",
    min_value=0.80, max_value=0.99, value=float(st.session_state.dupe_threshold), step=0.01,
    help="Names above this similarity are flagged for review. Increase if you see too many false positives."
)

col_scan, col_clear = st.columns(2)
with col_scan:
    if st.button("Scan for near‑duplicates"):
        st.session_state.dupe_pairs = find_near_dupes(players, threshold=st.session_state.dupe_threshold)
        st.session_state.dupe_decisions = {}
        st.session_state.dupe_scan_done = True
        st.session_state.cleaned_players = None  # reset
with col_clear:
    if st.button("Clear duplicate review"):
        st.session_state.dupe_pairs = []
        st.session_state.dupe_decisions = {}
        st.session_state.dupe_scan_done = False
        st.session_state.cleaned_players = None

if st.session_state.dupe_scan_done:
    if not st.session_state.dupe_pairs:
        st.success("No near‑duplicates detected at the current threshold.")
    else:
        st.info("Review each potential duplicate. Default is to keep both.")
        to_remove_indices = set()
        for k, pair in enumerate(st.session_state.dupe_pairs):
            st.markdown(
                f"**Possible duplicate:** {pair['a']}  ↔  {pair['b']} "
                f"(similarity: {pair['score']:.2f})"
            )
            choice = st.radio(
                f"Decision for pair {k+1}",
                options=("Keep both", f"Remove '{pair['a']}'", f"Remove '{pair['b']}'"),
                key=f"dupe_choice_{k}",
                horizontal=True
            )
            st.session_state.dupe_decisions[k] = choice

        if st.button("Apply decisions"):
            for k, pair in enumerate(st.session_state.dupe_pairs):
                choice = st.session_state.dupe_decisions.get(k, "Keep both")
                if choice == f"Remove '{pair['a']}'":
                    to_remove_indices.add(pair['i'])
                elif choice == f"Remove '{pair['b']}'":
                    to_remove_indices.add(pair['j'])

            st.session_state.cleaned_players = [
                name for idx, name in enumerate(players) if idx not in to_remove_indices
            ]
            removed_count = len(to_remove_indices)
            if removed_count:
                st.success(f"Applied decisions: removed {removed_count} entr{'y' if removed_count==1 else 'ies'}.")
            else:
                st.success("Applied decisions: kept all names.")

# =========================================================
# ------------------- Round creation ----------------------
# =========================================================
def create_round(pool, round_number, initial=False):
    """
    Returns a tuple: (matches, bye_players)
    - matches: list of (player1, player2)
    - bye_players: list of players who received a Round 1 bye (empty otherwise)
    """
    pool = pool[:]  # copy
    random.shuffle(pool)
    matches = []
    bye_players = []

    if round_number == 1 and initial:
        target = next_power_of_two(len(pool))
        byes_needed = target - len(pool)
        if byes_needed > 0:
            bye_players = pool[:byes_needed]
            for bp in bye_players:
                st.info(f"{bp} gets a bye in Round 1.")
                # Byes advance automatically as winners for the next round
                st.session_state.winners.append(bp)
            pool = pool[byes_needed:]
    else:
        if not is_power_of_two(len(pool)):
            st.error("Winners count must be a power of 2 from Round 2 onward.")
            return [], []

    for i in range(0, len(pool) - 1, 2):
        matches.append((pool[i], pool[i + 1]))
    return matches, bye_players

# =========================================================
# ------------------- Generate Fixtures -------------------
# =========================================================
st.divider()
if st.button("Generate Round Fixtures"):
    # Prefer the cleaned list (after duplicate review) if present; otherwise use raw input
    source_players = st.session_state.cleaned_players if st.session_state.cleaned_players else players

    # Optionally disambiguate exact identical names so they remain distinct everywhere
    if st.session_state.auto_disambiguate:
        source_players = disambiguate_duplicates(source_players)

    if st.session_state.round == 1:
        if st.session_state.winners:  # allow pasted results to act as entrants
            st.session_state.matches, st.session_state.byes = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.round_generated = True
            st.session_state.winners = []
        elif not source_players:
            st.warning("Please enter entrants first or paste results.")
        else:
            st.session_state.initial_players = source_players[:]
            st.session_state.winners = []
            st.session_state.matches, st.session_state.byes = create_round(
                source_players, round_number=1, initial=True
            )
            st.session_state.round_generated = True
    else:
        if not st.session_state.winners:
            st.warning("No winners to advance. Submit or paste match results first.")
        elif not is_power_of_two(len(st.session_state.winners)):
            st.error(f"Winners count is {len(st.session_state.winners)}; must be a power of 2.")
        else:
            st.session_state.matches, st.session_state.byes = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.round_generated = True
            st.session_state.winners = []

# =========================================================
# ---------- Display matches & record results -------------
# =========================================================
if st.session_state.matches:
    st.header(f"Round {st.session_state.round} Fixtures")
    scores = []
    for i, (p1, p2) in enumerate(st.session_state.matches):
        st.subheader(f"Match {i + 1}: {p1} vs {p2}")
        c1, c2 = st.columns(2)
        with c1:
            score1 = st.number_input(
                f"Score for {p1}", key=f"score1_{st.session_state.round}_{i}", step=1, min_value=0
            )
        with c2:
            score2 = st.number_input(
                f"Score for {p2}", key=f"score2_{st.session_state.round}_{i}", step=1, min_value=0
            )
        scores.append((p1, p2, score1, score2))

    if st.button("Submit All Results and Redraw Next Round"):
        current_round_results = []
        any_ties = False
        for p1, p2, s1, s2 in scores:
            if s1 == s2:
                st.error(f"Tie detected in {p1} vs {p2}. Please adjust scores.")
                any_ties = True
            else:
                winner = p1 if s1 > s2 else p2
                st.success(f"{p1} vs {p2} → {s1}-{s2}, Winner: {winner}")
                st.session_state.winners.append(winner)
                current_round_results.append((p1, p2, winner))

        if any_ties:
            st.stop()

        if current_round_results:
            st.session_state.history.append((st.session_state.round, current_round_results))

        if len(st.session_state.winners) == 1:
            st.header("🏆 Champion")
            st.success(f"The champion is {st.session_state.winners[0]}!")
        elif is_power_of_two(len(st.session_state.winners)):
            st.session_state.round += 1
            st.session_state.matches, st.session_state.byes = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.winners = []
            st.session_state.round_generated = True
            st.success(f"Fixtures for Round {st.session_state.round} generated automatically.")

# =========================================================
# --------------- Simple text output (copy) ---------------
# =========================================================
if st.session_state.matches:
    st.header("Copy & Paste Fixture List")
    fixture_lines = [f"{p1} vs {p2}" for p1, p2 in st.session_state.matches]

    if st.session_state.byes:
        fixture_lines.append("")  # blank line
        fixture_lines.append("The following players have byes:")
        fixture_lines.extend(st.session_state.byes)

    fixture_text = "\n".join(fixture_lines)
    st.text(fixture_text)

# =========================================================
# ---------------- Paste Spreadsheet Data -----------------
# =========================================================
st.header("Paste Spreadsheet Results")
st.caption("Format each line like:  A vs B = 1-4")
raw_data = st.text_area("Paste rows in format: A vs B = 1-4", height=150)

if st.button("Process Pasted Results"):
    lines = [line.strip() for line in raw_data.split("\n") if line.strip()]
    current_round_results = []
    for line in lines:
        try:
            match, result = line.split("=")
            p1, p2 = match.split("vs")
            p1, p2 = p1.strip(), p2.strip()
            s1, s2 = result.strip().split("-")
            s1, s2 = int(s1), int(s2)
            if s1 == s2:
                st.error(f"Tie detected in {p1} vs {p2}. Please adjust.")
                continue
            winner = p1 if s1 > s2 else p2
            st.write(f"{p1} vs {p2} → {s1}-{s2}, Winner: {winner}")
            st.session_state.winners.append(winner)
            current_round_results.append((p1, p2, winner))
        except Exception:
            st.error(f"Could not parse line: {line}")

    if current_round_results:
        st.session_state.history.append((st.session_state.round, current_round_results))

    if len(st.session_state.winners) == 1:
        st.header("🏆 Champion")
        st.success(f"The champion is {st.session_state.winners[0]}!")
    elif is_power_of_two(len(st.session_state.winners)):
        st.session_state.round += 1
        st.session_state.matches, st.session_state.byes = create_round(
            st.session_state.winners,
            round_number=st.session_state.round,
            initial=False
        )
        st.session_state.winners = []
        st.session_state.round_generated = True
        st.success(f"Fixtures for Round {st.session_state.round} generated automatically.")

# =========================================================
# ---------------- Bracket visualisation ------------------
# =========================================================
if st.session_state.history:
    st.header("Tournament Bracket View")

    # If auto-disambiguation is off and identical names exist, Graphviz would merge them.
    # We warn in that edge case.
    init_lower = [n.lower() for n in st.session_state.initial_players]
    if len(set(init_lower)) != len(init_lower) and not st.session_state.auto_disambiguate:
        st.warning(
            "Identical names detected without disambiguation. "
            "Graphviz may merge identical labels. Consider enabling auto‑disambiguation above."
        )

    dot = graphviz.Digraph()

    # Create initial player nodes
    for p in st.session_state.initial_players:
        dot.node(p, p, shape="box")  # use the (unique) name as both id and label

    # Create match nodes and connect edges
    for rnd, results in st.session_state.history:
        for idx, (p1, p2, winner) in enumerate(results, start=1):
            match_id = f"R{rnd}-M{idx}"
            label = f"R{rnd} M{idx}\n{p1} vs {p2}"
            dot.node(match_id, label, shape="ellipse")
            dot.edge(p1, match_id)
            dot.edge(p2, match_id)
            dot.edge(match_id, winner)

    st.graphviz_chart(dot)
``
