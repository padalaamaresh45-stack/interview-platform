/** Timezone conversion helpers shared by the scheduling picker and the
 * interviewer portal — given a UTC instant and an IANA zone name, produce
 * the local wall-clock time and short zone label for that zone specifically,
 * not whatever zone the viewer's own browser happens to be in. */

export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

export function formatTimeInZone(iso: string, timeZone: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
}

export function formatDateTimeInZone(iso: string, timeZone: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
}

/** Short zone label for a given instant in a given zone, e.g. "ET" or "IST" —
 * computed per-instant (not per-zone) since a zone's offset abbreviation can
 * change across a DST boundary. */
export function zoneAbbreviation(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat(undefined, { timeZone, timeZoneName: "short" }).formatToParts(
    new Date(iso),
  );
  return parts.find((p) => p.type === "timeZoneName")?.value ?? timeZone;
}
