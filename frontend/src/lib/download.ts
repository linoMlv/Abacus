/**
 * Trigger a browser download for a same-origin URL whose response carries a
 * `Content-Disposition: attachment` header. A transient anchor click keeps the
 * SPA in place (no navigation) and lets the server name the file.
 */
export function triggerDownload(url: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
}
