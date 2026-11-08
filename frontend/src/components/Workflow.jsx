import React from "react";
import { stages, validationFor } from "../model.js";
import { Icon } from "./ui.jsx";
export default function Workflow({ incident, selected, onSelect }) {
  function navigate(event, index) {
    const offset = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    let next = offset
      ? (index + offset + stages.length) % stages.length
      : event.key === "Home"
        ? 0
        : event.key === "End"
          ? stages.length - 1
          : null;
    if (next === null) return;
    event.preventDefault();
    onSelect(stages[next].id);
    document.getElementById(`agent-tab-${stages[next].id}`)?.focus();
  }
  return (
    <section className="workflow">
      <div className="section-label">
        <span>INVESTIGATION WORKFLOW</span>
        <small>Agent 4 coordinates and validates all stages</small>
      </div>
      <div
        className="workflow-rail"
        role="tablist"
        aria-label="Five-agent workflow"
      >
        {stages.map((stage, i) => {
          const status = validationFor(incident, stage.step);
          return (
            <button
              key={stage.id}
              id={`agent-tab-${stage.id}`}
              role="tab"
              aria-selected={selected === stage.id}
              aria-controls="agent-panel"
              tabIndex={selected === stage.id ? 0 : -1}
              onKeyDown={(e) => navigate(e, i)}
              onClick={() => onSelect(stage.id)}
              className={`workflow-step ${selected === stage.id ? "selected" : ""}`}
            >
              <span className="step-number">{i + 1}</span>
              <span>
                <strong>{stage.name}</strong>
                <small className={status.tone}>{status.label}</small>
              </span>
              <Icon name="arrow" size={14} />
            </button>
          );
        })}
      </div>
      <p className="workflow-caption">
        Inspect saved results. These tabs do not simulate live execution.
      </p>
    </section>
  );
}
