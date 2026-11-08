import React from "react";
import { humanize } from "../model.js";

export function Icon({ name = "shield", size = 20 }) {
  const paths = {
    shield: "M12 3 4 6v6c0 4 8 9 8 9s8-5 8-9V6l-8-3Z",
    activity: "M3 12h4l3-8 4 16 3-8h4",
    search: "m16 16 5 5M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z",
    arrow: "m9 5 7 7-7 7",
    play: "m8 5 11 7-11 7V5Z",
    refresh:
      "M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3",
    check: "m5 12 4 4L19 6",
    close: "m6 6 12 12M6 18 18 6",
    download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
    server: "M4 3h16v7H4V3Zm0 11h16v7H4v-7ZM7 6h1m-1 11h1",
    spark: "m12 3 2 7 7 2-7 2-2 7-2-7-7-2 7-2 2-7Z",
    logout: "M9 4H4v16h5m5-13 5 5-5 5m-5-5h10",
    info: "M12 11v6m0-10v1M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z",
  };
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
    >
      <path d={paths[name] || paths.shield} />
    </svg>
  );
}
export function Badge({ children, tone = "neutral", dot = false }) {
  return (
    <span className={`badge ${tone}`}>
      {dot && <i />}
      {children}
    </span>
  );
}
export function Severity({ value }) {
  return (
    <Badge
      tone={
        ["high", "critical"].includes(value)
          ? "danger"
          : value === "medium"
            ? "warning"
            : "neutral"
      }
      dot
    >
      {humanize(value)}
    </Badge>
  );
}
export function Button({
  children,
  icon,
  variant = "secondary",
  busy,
  ...props
}) {
  return (
    <button
      className={`btn ${variant}`}
      aria-busy={busy || undefined}
      {...props}
    >
      {busy ? (
        <span className="spinner" aria-hidden="true" />
      ) : (
        icon && <Icon name={icon} size={16} />
      )}
      {children}
    </button>
  );
}
export function Panel({ title, subtitle, aside, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      <div className="card-heading">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}
export function Empty({ title = "Not available in this report", children }) {
  return (
    <div className="empty">
      <Icon name="info" />
      <strong>{title}</strong>
      <p>
        {children ||
          "The backend did not supply this information. No result has been inferred."}
      </p>
    </div>
  );
}
export function Chips({ ids = [] }) {
  return ids.length ? (
    <div className="chips">
      {[...new Set(ids)].map((id) => (
        <code key={id}>{id}</code>
      ))}
    </div>
  ) : (
    <span className="muted">No IDs supplied</span>
  );
}
export function Facts({ items = [], empty }) {
  return items.length ? (
    <ul className="fact-list">
      {items.map((text, i) => (
        <li key={i}>
          {typeof text === "string" ? text : JSON.stringify(text)}
        </li>
      ))}
    </ul>
  ) : (
    <Empty>{empty}</Empty>
  );
}
export function KeyValues({ items }) {
  return (
    <dl className="key-values">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value ?? <span className="muted">Not supplied</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
export function StageIntro({ stage, validation }) {
  return (
    <div className="stage-intro">
      <div>
        <span className="eyebrow">AGENT WORKSPACE</span>
        <h2>{stage.title}</h2>
        <p>{stage.subtitle}</p>
      </div>
      <Badge tone={validation.tone}>{validation.label}</Badge>
      <div className="io-grid">
        <div>
          <small>INPUT</small>
          <p>{stage.input}</p>
        </div>
        <div>
          <small>OUTPUT</small>
          <p>{stage.output}</p>
        </div>
        <div>
          <small>WHY IT MATTERS</small>
          <p>{stage.why}</p>
        </div>
      </div>
    </div>
  );
}
export function ErrorNotice({ message }) {
  return message ? (
    <div className="notice danger" role="alert">
      <Icon name="info" />
      <span>{message}</span>
    </div>
  ) : null;
}
