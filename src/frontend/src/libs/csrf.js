function getCSRFToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta?.getAttribute("content") ?? "";
}

export default getCSRFToken;
