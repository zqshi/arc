import { PROJECTS, type SeedProject } from './data';
import { buildPipeline, buildPartialPipeline, type PipelineData } from './pipeline-data';
import { EXPERIENCES } from './experience-data';
import { randomUUID } from 'crypto';

const API = process.env.API_URL || 'http://localhost:8000';
const DB_URL = process.env.DATABASE_URL || 'postgresql://zqs@localhost:5432/arc';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

async function sql(query: string): Promise<string> {
  const { execSync } = await import('child_process');
  return execSync(`psql "${DB_URL}" -tAc "${query.replace(/"/g, '\\"')}"`, { stdio: 'pipe' }).toString().trim();
}

async function sqlMulti(query: string): Promise<void> {
  const { execSync } = await import('child_process');
  const { writeFileSync, unlinkSync } = await import('fs');
  const { tmpdir } = await import('os');
  const { join } = await import('path');
  const tmpFile = join(tmpdir(), `arc-seed-${Date.now()}.sql`);
  writeFileSync(tmpFile, query);
  try {
    execSync(`psql "${DB_URL}" -f "${tmpFile}"`, { stdio: 'pipe' });
  } finally {
    unlinkSync(tmpFile);
  }
}

function esc(s: string): string {
  return s.replace(/'/g, "''");
}

function jsonEsc(obj: unknown): string {
  return esc(JSON.stringify(obj));
}

async function cleanAll() {
  console.log('\n🧹 清理数据...');
  const tables = [
    'experience_feedback', 'experiences', 'messages', 'conversations',
    'agent_sessions', 'artifacts', 'pipeline_phases', 'todos', 'versions', 'projects',
  ];
  await sqlMulti(tables.map((t) => `TRUNCATE TABLE ${t} CASCADE;`).join(' '));
  console.log('   已清空');
}

async function injectPipeline(todoId: string, pipeline: PipelineData[]): Promise<void> {
  const now = new Date().toISOString();
  const stmts: string[] = [];

  for (const phase of pipeline) {
    const phaseId = randomUUID();
    let convId: string | null = null;

    // Create conversation + messages if phase has messages
    if (phase.messages && phase.messages.length > 0) {
      convId = randomUUID();
      stmts.push(
        `INSERT INTO conversations (id, todo_id, purpose, created_at) VALUES ('${convId}', '${todoId}', '${phase.phase_type}', '${now}');`
      );
      for (const msg of phase.messages) {
        const msgId = randomUUID();
        stmts.push(
          `INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES ('${msgId}', '${convId}', '${msg.role}', '${esc(msg.content)}', '${now}');`
        );
      }
    }

    // Create pipeline phase
    const convRef = convId ? `'${convId}'` : 'NULL';
    stmts.push(
      `INSERT INTO pipeline_phases (id, todo_id, phase_type, status, conversation_id, created_at, updated_at) VALUES ('${phaseId}', '${todoId}', '${phase.phase_type}', '${phase.status}', ${convRef}, '${now}', '${now}');`
    );

    // Create artifact if present
    if (phase.artifact) {
      const artId = randomUUID();
      const confirmed = phase.artifact.is_confirmed;
      const confirmedAt = confirmed ? `'${now}'` : 'NULL';
      stmts.push(
        `INSERT INTO artifacts (id, todo_id, phase_id, artifact_type, content, version, is_confirmed, confirmed_at, created_at, updated_at) VALUES ('${artId}', '${todoId}', '${phaseId}', '${phase.artifact.artifact_type}', '${jsonEsc(phase.artifact.content)}', 1, ${confirmed}, ${confirmedAt}, '${now}', '${now}');`
      );
    }
  }

  // Execute all in one transaction
  const transaction = `BEGIN; ${stmts.join(' ')} COMMIT;`;
  await sqlMulti(transaction);
}

// Decide pipeline progress based on project/version status
function getPipelineProgress(projectIdx: number, versionIdx: number, todoIdx: number): string | 'full' | 'none' {
  // Project 0 (Arc): v1.0 = full done, v1.1 = mixed progress
  if (projectIdx === 0) {
    if (versionIdx === 0) return 'full';
    // v1.1: first todo at development, second at architecture, third at clarification
    return ['development', 'architecture', 'clarification'][todoIdx] || 'clarification';
  }
  // Project 1 (智能客服): v0.1 active — mixed progress
  if (projectIdx === 1) {
    return ['architecture', 'ui_design', 'clarification', 'clarification'][todoIdx] || 'clarification';
  }
  // Project 2 (数据分析): planning — just started pipeline
  if (projectIdx === 2) {
    return 'clarification';
  }
  // Project 3 (Legacy): released — all done
  if (projectIdx === 3) return 'full';
  // Project 4 (设计系统): v0.1 released = full, v0.2 active = mixed
  if (projectIdx === 4) {
    if (versionIdx === 0) return 'full';
    return ['development', 'ui_design', 'clarification'][todoIdx] || 'clarification';
  }
  return 'none';
}

// Track created IDs for experience linking
const createdProjects: string[] = []; // index matches PROJECTS array
const createdTodos: string[][][] = []; // [projectIdx][versionIdx][todoIdx] = todoId

async function seedProject(def: SeedProject, projectIdx: number) {
  console.log(`\n📦 ${def.name}`);

  const project = await request<{ id: string }>('/api/projects', {
    method: 'POST',
    body: JSON.stringify({
      name: def.name,
      description: def.description,
      tech_stack: def.tech_stack,
      repo_url: def.repo_url,
      conventions: def.conventions,
    }),
  });
  const pid = project.id;
  createdProjects[projectIdx] = pid;
  createdTodos[projectIdx] = [];

  for (let vi = 0; vi < def.versions.length; vi++) {
    const vDef = def.versions[vi];
    const version = await request<{ id: string; name: string }>(`/api/projects/${pid}/versions`, {
      method: 'POST',
      body: JSON.stringify({ goal: vDef.goal, version_type: vDef.version_type, name: vDef.name }),
    });
    const vid = version.id;
    createdTodos[projectIdx][vi] = [];

    console.log(`   📌 ${version.name} — ${vDef.goal.slice(0, 35)}...`);

    for (let ti = 0; ti < vDef.todos.length; ti++) {
      const tDef = vDef.todos[ti];
      const todo = await request<{ id: string }>('/api/todos', {
        method: 'POST',
        body: JSON.stringify({
          title: tDef.title,
          description: tDef.description,
          project_id: pid,
          version_id: vid,
          tags: tDef.tags,
        }),
      });
      createdTodos[projectIdx][vi][ti] = todo.id;

      const progress = getPipelineProgress(projectIdx, vi, ti);

      if (progress === 'none') {
        console.log(`      ✏️  ${tDef.title} (无Pipeline)`);
        continue;
      }

      let pipeline: PipelineData[];
      let todoStatus: string;

      if (progress === 'full') {
        pipeline = buildPipeline(tDef.title, tDef.description, def.name);
        todoStatus = 'done';
      } else {
        pipeline = buildPartialPipeline(tDef.title, tDef.description, def.name, progress);
        todoStatus = 'active';
      }

      await injectPipeline(todo.id, pipeline);

      // Update todo status and current_phase
      const currentPhase = progress === 'full' ? 'extraction' : progress;
      await sqlMulti(
        `UPDATE todos SET status = '${todoStatus}', current_phase = '${currentPhase}' WHERE id = '${todo.id}';`
      );

      const phaseLabel = progress === 'full' ? '✅全部完成' : `🔄${progress}`;
      console.log(`      ✏️  ${tDef.title} (${phaseLabel})`);
    }

    // Set version status
    if (vDef.release) {
      await sqlMulti(`UPDATE versions SET status = 'released' WHERE id = '${vid}';`);
    } else if (vDef.activate) {
      await sqlMulti(`UPDATE versions SET status = 'active' WHERE id = '${vid}';`);
    }
  }

  if (def.archive) {
    await sqlMulti(`UPDATE projects SET status = 'archived' WHERE id = '${pid}';`);
    console.log(`   📁 已归档`);
  }
}

async function seedExperiences() {
  const now = new Date().toISOString();
  const stmts: string[] = [];
  const expIds: string[] = [];

  for (const exp of EXPERIENCES) {
    const id = randomUUID();
    expIds.push(id);
    const projectId = exp.projectIdx !== null ? `'${createdProjects[exp.projectIdx]}'` : 'NULL';
    const todoId = exp.todoRef && exp.projectIdx !== null
      ? `'${createdTodos[exp.projectIdx][exp.todoRef.versionIdx][exp.todoRef.todoIdx]}'`
      : 'NULL';
    const decisions = exp.decisions.length > 0 ? `'${jsonEsc(exp.decisions)}'` : 'NULL';
    const pitfalls = exp.pitfalls.length > 0 ? `'${jsonEsc(exp.pitfalls)}'` : 'NULL';
    const tags = exp.tags.length > 0 ? `'${jsonEsc(exp.tags)}'` : 'NULL';

    stmts.push(
      `INSERT INTO experiences (id, todo_id, project_id, title, scope, status, problem, solution, decisions, pitfalls, applicable_scenarios, tags, confidence, reuse_count, created_at, updated_at) VALUES ('${id}', ${todoId}, ${projectId}, '${esc(exp.title)}', '${exp.scope}', '${exp.status}', '${esc(exp.problem)}', '${esc(exp.solution)}', ${decisions}, ${pitfalls}, '${esc(exp.applicable_scenarios)}', ${tags}, ${exp.confidence}, ${exp.reuse_count}, '${now}', '${now}');`
    );

    console.log(`   💡 ${exp.title} (${exp.status}/${exp.scope})`);
  }

  // Add some feedback records for confirmed experiences
  const feedbackPairs: { expIdx: number; todoProjectIdx: number; todoVersionIdx: number; todoTodoIdx: number; helpful: boolean }[] = [
    { expIdx: 0, todoProjectIdx: 1, todoVersionIdx: 0, todoTodoIdx: 0, helpful: true },
    { expIdx: 1, todoProjectIdx: 0, todoVersionIdx: 1, todoTodoIdx: 1, helpful: true },
    { expIdx: 2, todoProjectIdx: 1, todoVersionIdx: 0, todoTodoIdx: 1, helpful: true },
    { expIdx: 5, todoProjectIdx: 0, todoVersionIdx: 1, todoTodoIdx: 0, helpful: true },
    { expIdx: 7, todoProjectIdx: 0, todoVersionIdx: 1, todoTodoIdx: 0, helpful: false },
    { expIdx: 8, todoProjectIdx: 0, todoVersionIdx: 0, todoTodoIdx: 2, helpful: true },
  ];

  for (const fb of feedbackPairs) {
    const fbId = randomUUID();
    const todoId = createdTodos[fb.todoProjectIdx][fb.todoVersionIdx][fb.todoTodoIdx];
    stmts.push(
      `INSERT INTO experience_feedback (id, experience_id, todo_id, helpful, created_at, updated_at) VALUES ('${fbId}', '${expIds[fb.expIdx]}', '${todoId}', ${fb.helpful}, '${now}', '${now}');`
    );
  }

  const transaction = `BEGIN; ${stmts.join(' ')} COMMIT;`;
  await sqlMulti(transaction);
  console.log(`   ✅ ${EXPERIENCES.length} 条经验, ${feedbackPairs.length} 条反馈`);
}

async function main() {
  console.log('═══════════════════════════════════════════════');
  console.log(' Arc Seed — 全链路验证数据 (Pipeline+产出物)');
  console.log(`═══════════════════════════════════════════════`);

  if (process.argv.includes('--clean')) {
    await cleanAll();
  }

  for (let i = 0; i < PROJECTS.length; i++) {
    await seedProject(PROJECTS[i], i);
  }

  // ── Inject experiences ──
  console.log('\n📚 注入经验数据...');
  await seedExperiences();

  const stats = await sql(
    `SELECT (SELECT count(*) FROM projects) || ' 项目, ' || (SELECT count(*) FROM todos) || ' 需求, ' || (SELECT count(*) FROM pipeline_phases) || ' 阶段, ' || (SELECT count(*) FROM artifacts) || ' 产出物, ' || (SELECT count(*) FROM messages) || ' 消息, ' || (SELECT count(*) FROM experiences) || ' 经验'`
  );
  console.log(`\n✅ 完成！${stats}\n`);
}

main().catch((err) => {
  console.error('\n❌ 失败:', err.message);
  process.exit(1);
});
