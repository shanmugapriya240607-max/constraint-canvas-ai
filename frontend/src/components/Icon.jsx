const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  plus: "M12 5v14 M5 12h14",
  history: "M3 11a9 9 0 1 1 2.6 7 M3 4v7h7 M12 7v5l3 2",
  branch: "M6 3v12a4 4 0 0 0 4 4h8 M6 9h8a4 4 0 0 0 4-4V3 M15 16l3 3-3 3",
  memory: "M8 3H5v6H3v6h2v6h6V3z M16 3h3v6h2v6h-2v6h-6V3z",
  settings:
    "M9 3h6l1 4 4 2v6l-4 2-1 4H9l-1-4-4-2V9l4-2z M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  logout: "M9 4H4v16h5 M10 12h11 M17 8l4 4-4 4",
  layers: "m12 3 10 5-10 5L2 8z M2 12l10 5 10-5 M2 16l10 5 10-5",
  alert: "m12 3 10 18H2z M12 9v5 M12 17v1",
  pulse: "M2 12h5l3-8 4 16 3-8h5",
  lock: "M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0v4",
  menu: "M3 6h18 M3 12h18 M3 18h18",
  close: "m6 6 12 12 M6 18 18 6",
  check: "m5 12 4 4L19 6",
};
export default function Icon({ name, size = 20, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name] || paths.grid} />
    </svg>
  );
}
