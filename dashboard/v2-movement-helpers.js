(function attachMovementHelpers(root, factory) {
  const helpers = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports.buildPickedSideMovement = helpers.buildPickedSideMovement;
    module.exports.summarizeLineMovement = helpers.summarizeLineMovement;
    module.exports.parkFactorTone = helpers.parkFactorTone;
  }

  if (root) {
    root.V2MovementHelpers = helpers;
  }
})(
  typeof globalThis !== "undefined"
    ? globalThis
    : typeof window !== "undefined"
      ? window
      : this,
  function createMovementHelpers() {
    function buildPickedSideMovement(steam, pick) {
      const snapshots = Array.isArray(steam?.snapshots) ? steam.snapshots : [];
      const direction = pick?.direction === "UNDER" ? "UNDER" : "OVER";
      const oddsKey = direction === "OVER" ? "over" : "under";
      const selectedBook = typeof pick?.selectedBook === "string" ? pick.selectedBook : null;
      const points = [];
      const openingOdds = pick?.openingOdds;
      const openingLine = pick?.openingLine;
      let bookUsed = null;

      for (const snapshot of snapshots) {
        const entry = snapshot?.pitchers?.[pick?.pitcher];
        const books = entry && typeof entry === "object"
          ? Object.keys(entry).filter((key) => key !== "k_line")
          : [];
        const bookCandidates = [
          selectedBook,
          "FanDuel",
          ...books,
        ].filter((book, idx, arr) => book && arr.indexOf(book) === idx);
        const book = bookCandidates.find((candidate) => entry?.[candidate]?.[oddsKey] != null);
        const odds = book ? entry?.[book]?.[oddsKey] : null;
        const kLine = entry?.k_line;

        if (snapshot?.t == null || odds == null || kLine == null) {
          continue;
        }

        bookUsed = bookUsed || book;
        points.push({
          t: snapshot.t,
          odds,
          kLine,
          book,
        });
      }

      if (openingOdds != null && openingLine != null) {
        const first = points[0];
        const openingDiffers =
          !first ||
          first.odds !== openingOdds ||
          first.kLine !== openingLine;

        if (openingDiffers) {
          points.unshift({
            t: "open",
            odds: openingOdds,
            kLine: openingLine,
            book: bookUsed || selectedBook || "FanDuel",
            synthetic: true,
          });
        }
      }

      if (points.length < 2) {
        return {
          ready: false,
          reason: "insufficient_history",
          book: bookUsed || selectedBook || "FanDuel",
          direction,
          points,
        };
      }

      return {
        ready: true,
        reason: null,
        book: bookUsed || selectedBook || "FanDuel",
        direction,
        points,
      };
    }

    function summarizeLineMovement(movement) {
      const points = Array.isArray(movement?.points) ? movement.points : [];
      const first = points[0];
      const last = points[points.length - 1];

      if (!first || !last) {
        return null;
      }

      return {
        lineMoved: first.kLine !== last.kLine,
        openingLine: first.kLine,
        currentLine: last.kLine,
        openingOdds: first.odds,
        currentOdds: last.odds,
      };
    }

    function parkFactorTone(parkFactor, direction) {
      if (parkFactor == null) {
        return "neutral";
      }

      if (parkFactor > 1.02) {
        return direction === "OVER" ? "pos" : "neg";
      }

      if (parkFactor < 0.98) {
        return direction === "UNDER" ? "pos" : "neg";
      }

      return "neutral";
    }

    return {
      buildPickedSideMovement,
      summarizeLineMovement,
      parkFactorTone,
    };
  },
);
