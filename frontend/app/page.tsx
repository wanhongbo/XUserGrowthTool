"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  Clipboard,
  DatabaseZap,
  FileText,
  Inbox,
  MessageSquareText,
  RefreshCw,
  ShieldCheck,
  UserRoundCheck,
  XCircle,
} from "lucide-react";
import {
  EngagementTask,
  LeadCandidate,
  Overview,
  getLeads,
  getOverview,
  getTasks,
  optOut,
  regenerateDraft,
  runSampleDiscovery,
  updateTask,
} from "@/lib/api";

const nav = [
  ["Discover", DatabaseZap],
  ["Review", Inbox],
  ["Public Queue", MessageSquareText],
  ["DM Drafts", FileText],
  ["Compliance", ShieldCheck],
] as const;

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [leads, setLeads] = useState<LeadCandidate[]>([]);
  const [tasks, setTasks] = useState<EngagementTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const [overviewData, leadData, taskData] = await Promise.all([getOverview(), getLeads(), getTasks()]);
      setOverview(overviewData);
      setLeads(leadData);
      setTasks(taskData);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to load workspace");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const topLeads = useMemo(() => leads.slice(0, 8), [leads]);
  const activeTasks = useMemo(() => tasks.filter((task) => !["done", "rejected", "opt_out"].includes(task.status)), [tasks]);

  async function seed() {
    setNotice("Running sample discovery...");
    try {
      const result = await runSampleDiscovery();
      setNotice(`Discovery complete: ${result.users_upserted} users, ${result.posts_upserted} posts, ${result.tasks_created} new tasks.`);
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Discovery failed");
    }
  }

  async function taskAction(task: EngagementTask, status: EngagementTask["status"]) {
    try {
      await updateTask(task.id, { status });
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Task update failed");
    }
  }

  async function updateDraft(task: EngagementTask, draft: string) {
    setTasks((current) => current.map((item) => (item.id === task.id ? { ...item, draft } : item)));
    await updateTask(task.id, { draft });
  }

  async function blockUser(task: EngagementTask) {
    await optOut(task.user.x_user_id, "Manual opt-out from operator queue");
    await refresh();
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">X Circle Operator</div>
        <p className="muted" style={{ color: "#bdb5a5", marginTop: 10 }}>
          Human-reviewed growth ops for privacy and cybersecurity circles.
        </p>
        <nav className="nav-stack" aria-label="Main workflow">
          {nav.map(([label, Icon], index) => (
            <a className={`nav-item ${index === 0 ? "active" : ""}`} href={`#${label.toLowerCase().replaceAll(" ", "-")}`} key={label}>
              <Icon size={18} aria-hidden="true" />
              {label}
            </a>
          ))}
        </nav>
      </aside>

      <section className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">Compliance-first outreach desk</div>
            <h1>Find active privacy people, then keep the human in the send path.</h1>
            <p className="muted" style={{ marginTop: 10, maxWidth: 720 }}>
              Discovery, scoring, suggestions, and draft prep are automated. Replies and DMs are reviewed and sent manually.
            </p>
          </div>
          <div className="toolbar">
            <button className="secondary-button" type="button" onClick={refresh} disabled={loading}>
              <RefreshCw size={17} aria-hidden="true" />
              Refresh
            </button>
            <button className="primary-button" type="button" onClick={seed}>
              <DatabaseZap size={17} aria-hidden="true" />
              Run Sample Discovery
            </button>
          </div>
        </header>

        {notice ? <div className="policy-band"><AlertTriangle size={22} aria-hidden="true" /><p>{notice}</p></div> : null}

        <section className="metric-grid" aria-label="Overview metrics">
          <Metric label="Leads" value={overview?.leads ?? 0} />
          <Metric label="Review" value={overview?.review_tasks ?? 0} />
          <Metric label="Public" value={overview?.public_tasks ?? 0} />
          <Metric label="DM Drafts" value={overview?.dm_tasks ?? 0} />
          <Metric label="Opt-outs" value={overview?.opt_outs ?? 0} />
          <Metric label="Blocked DM" value={overview?.compliance_blocks ?? 0} />
        </section>

        <section className="policy-band" id="compliance">
          <ShieldCheck size={24} aria-hidden="true" />
          <div>
            <h2>Hard Compliance Gates</h2>
            <p className="muted" style={{ marginTop: 6 }}>
              No scraping, no browser automation, no bulk automated replies, no automated likes/follows, and no unsolicited DM queue. DM drafts require explicit public contact intent or an existing user-initiated channel.
            </p>
          </div>
        </section>

        <div className="workspace">
          <section className="section" id="discover">
            <div className="section-head">
              <h2>Top Leads</h2>
              <span className="badge">{loading ? "Loading" : `${topLeads.length} visible`}</span>
            </div>
            <div className="lead-list">
              {topLeads.length ? topLeads.map((lead) => <LeadRow lead={lead} key={lead.user.x_user_id} />) : <Empty text="Run sample discovery or connect an X API token." />}
            </div>
          </section>

          <section className="section" id="review">
            <div className="section-head">
              <h2>Human Review Queue</h2>
              <span className="badge">{activeTasks.length} active</span>
            </div>
            <div className="task-list">
              {activeTasks.length ? (
                activeTasks.map((task) => (
                  <TaskRow
                    task={task}
                    key={task.id}
                    onStatus={(status) => taskAction(task, status)}
                    onDraft={(draft) => updateDraft(task, draft)}
                    onRegenerate={async () => {
                      await regenerateDraft(task.id);
                      await refresh();
                    }}
                    onOptOut={() => blockUser(task)}
                  />
                ))
              ) : (
                <Empty text="No active tasks yet." />
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LeadRow({ lead }: { lead: LeadCandidate }) {
  const score = lead.user.score?.final_score ?? 0;
  const dm = lead.user.dm_eligibility;
  return (
    <article className="lead-row">
      <div>
        <h3>
          {lead.user.name} <span className="muted">@{lead.user.username}</span>
        </h3>
        <p className="muted" style={{ marginTop: 5 }}>{lead.user.bio || "No bio captured"}</p>
        <div className="badges">
          <span className="badge">{lead.open_tasks} open task(s)</span>
          <span className={`badge ${dm?.is_eligible ? "good" : "warn"}`}>{dm?.is_eligible ? "DM eligible" : "DM blocked"}</span>
          {lead.user.verified ? <span className="badge good"><UserRoundCheck size={13} aria-hidden="true" /> verified</span> : null}
          {lead.user.score?.risk ? <span className={`badge ${lead.user.score.risk > 40 ? "danger" : "warn"}`}>risk {lead.user.score.risk}</span> : null}
        </div>
        {lead.posts[0] ? <p className="post-text">{lead.posts[0].text}</p> : null}
        {lead.user.score?.reason ? <p className="muted" style={{ marginTop: 10 }}>{lead.user.score.reason}</p> : null}
      </div>
      <div className="score" aria-label={`Score ${score}`}>{Math.round(score)}</div>
    </article>
  );
}

function TaskRow({
  task,
  onStatus,
  onDraft,
  onRegenerate,
  onOptOut,
}: {
  task: EngagementTask;
  onStatus: (status: EngagementTask["status"]) => void;
  onDraft: (draft: string) => void;
  onRegenerate: () => void;
  onOptOut: () => void;
}) {
  const isDm = task.task_type === "dm_draft";
  const dmAllowed = task.user.dm_eligibility?.is_eligible && !task.user.opt_out;
  return (
    <article className="task-row">
      <div className="section-head">
        <div>
          <h3>
            {isDm ? "DM draft" : "Public interaction"} for @{task.user.username}
          </h3>
          <div className="task-meta">
            <span className="badge">{task.status}</span>
            <span className={`badge ${isDm && !dmAllowed ? "danger" : "good"}`}>{isDm ? (dmAllowed ? "eligible evidence present" : "blocked by DM gate") : "manual send only"}</span>
          </div>
        </div>
        <button className="icon-button" type="button" title="Regenerate draft" onClick={onRegenerate}>
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </div>
      {task.source_post ? <p className="post-text">{task.source_post.text}</p> : null}
      <p className="muted">{task.compliance_warning}</p>
      <textarea aria-label={`Draft for ${task.user.username}`} value={task.draft} onChange={(event) => onDraft(event.target.value)} />
      <div className="task-actions">
        <button className="status-button" type="button" onClick={() => navigator.clipboard.writeText(task.draft)}>
          <Clipboard size={16} aria-hidden="true" />
          Copy
        </button>
        <button className="status-button" type="button" onClick={() => onStatus(isDm ? "dm_draft" : "engage_publicly")} disabled={isDm && !dmAllowed}>
          <MessageSquareText size={16} aria-hidden="true" />
          Approve
        </button>
        <button className="status-button" type="button" onClick={() => onStatus("done")} disabled={isDm && !dmAllowed}>
          <Check size={16} aria-hidden="true" />
          Mark Done
        </button>
        <button className="status-button" type="button" onClick={() => onStatus("snoozed")}>
          <Inbox size={16} aria-hidden="true" />
          Snooze
        </button>
        <button className="status-button" type="button" onClick={() => onStatus("rejected")}>
          <XCircle size={16} aria-hidden="true" />
          Reject
        </button>
        <button className="status-button" type="button" onClick={onOptOut}>
          <AlertTriangle size={16} aria-hidden="true" />
          Opt-out
        </button>
      </div>
    </article>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}
