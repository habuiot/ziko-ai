class ZikoOperatorPanel extends HTMLElement {
  set hass(value) {
    this._hass = value;
    if (!this._started && this.isConnected) { this._started = true; this.load(); }
  }
  connectedCallback() { if (this._hass && !this._started) { this._started = true; this.load(); } }
  el(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (parent) parent.append(node);
    return node;
  }
  async call(operation, args = {}) {
    return this._hass.callWS({type: 'ziko_ha_tools/operator', operation, args});
  }
  async load() {
    this.replaceChildren();
    const style = this.el('style');
    style.textContent = ':host{display:block;box-sizing:border-box;max-width:1050px;margin:auto;padding:24px;color:var(--primary-text-color);font:16px/1.5 system-ui}section{padding:18px;margin:16px 0;border:1px solid var(--divider-color);border-radius:16px;background:var(--card-background-color)}button,a{display:inline-block;margin:5px;padding:10px 14px;border:1px solid var(--divider-color);border-radius:9px;color:var(--primary-text-color);background:var(--secondary-background-color);cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}h1,h2,h3{line-height:1.3}small{opacity:.75}.warning{border-left:4px solid #d59a33}';
    this.append(style);
    this.el('h1', 'Ziko központ', this);
    this.message = this.el('p', 'Állapot betöltése…', this);
    try { this.state = await this.call('status'); this.render(); }
    catch (error) { this.message.textContent = `Nem sikerült betölteni. A beállításokban rögzített HA-tulajdonossal nyisd meg. ${error.message || ''}`; }
  }
  button(parent, label, action) {
    const button = this.el('button', label, parent);
    button.onclick = async () => {
      button.disabled = true;
      try { await action(); }
      catch (error) { this.message.textContent = `A művelet nem igazolt: ${error.message || error}. Ellenőrizd az állapotot ismétlés előtt.`; }
      finally { button.disabled = false; }
    };
    return button;
  }
  section(title) { const section = this.el('section', undefined, this); this.el('h2', title, section); return section; }
  async perform(operation, args) {
    const result = await this.call(operation, args);
    await this.load();
    this.message.textContent = `Eredmény: ${result.status || (result.paused ? 'Ziko-írások szünetelnek' : 'mentve')}. ${result.note || ''}`;
  }
  download(name, data) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
    const link = this.el('a'); link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  render() {
    const s = this.state;
    this.message.textContent = `Ziko HA Tools ${s.version} · ${s.entity_count} olvasható entitás · ${s.areas.map(a => a.name).join(', ')}`;
    const setup = this.section('Indítás és beállítások');
    this.el('p', `Memória: ${s.memory_enabled ? 'bekapcsolva' : 'ki'} · Eszközírás: ${s.writes_enabled ? 'bekapcsolva' : 'ki'} · Automatizálási tervek: ${s.automation_drafts ? 'bekapcsolva' : 'ki'}`, setup);
    const links = [['Ziko-integráció beállításai','/config/integrations/integration/ziko_ha_tools'],['Hangasszisztensek','/config/voice-assistants'],['Automatizálások','/config/automation/dashboard'],['HACS','/hacs']];
    for (const [label, path] of links) { const a = this.el('a', label, setup); a.href = path; }
    this.button(setup, 'Állapot frissítése', () => this.load());
    this.button(setup, s.paused ? 'Ziko-írások folytatása' : 'Ziko-írások szüneteltetése', () => this.perform('pause', {paused: !s.paused}));
    this.el('p', 'A szüneteltetés a Ziko-bővítés írásait érinti. A meglévő HA-automatizálások és a natív Assist vezérlés külön működnek.', setup);
    this.el('small', 'A közös memória háztartási adat. A releváns tartalma beszélgetéskor az AI-szolgáltatóhoz kerülhet. Személyes naplót és jelszót ne tárolj itt.', setup);
    const components = this.section('Telepített építőelemek');
    for (const [domain, loaded] of Object.entries(s.components)) this.el('p', `${loaded ? '✓' : '○'} ${domain}: ${loaded ? 'HA-komponens betöltve' : 'nincs betöltve'}`, components);
    this.el('small', 'A betöltött állapot még nem igazolja a mikrofon, a hangszóró vagy a felhős kapcsolat élő próbáját.', components);
    if (s.bridge_errors.length) this.el('pre', s.bridge_errors.join('\n'), components);
    const memory = this.section('Közös memória és fénybeállítások');
    this.button(memory, 'Teljes helyi export letöltése', async () => this.download('Ziko_helyi_export.json', await this.call('export')));
    for (const record of [...s.facts, ...s.presets]) {
      const item = this.el('section', undefined, memory);
      this.el('h3', `${record.kind === 'fact' ? 'Emlék' : 'Fénypreset'}: ${record.key} · v${record.version}`, item);
      this.el('pre', JSON.stringify(record.value, null, 2), item);
      this.button(item, 'Törlés', async () => {
        if (confirm(`Törlöd ezt: ${record.key}?`)) await this.perform('delete', {kind: record.kind, key: record.key, version: record.version});
      });
    }
    const plans = this.section('Áttekintendő automatizálási tervek');
    if (!s.plans.length) this.el('p', 'Kérd Zikótól egy automatizálási terv elkészítését. A terv önmagában nem kapcsol be semmit.', plans);
    for (const plan of s.plans) {
      const item = this.el('section', undefined, plans);
      this.el('h3', `${plan.value.config.alias} · ${plan.value.status}`, item);
      this.el('h3', 'Jóváhagyandó feltételek és konkrét eszközműveletek', item);
      this.el('pre', JSON.stringify(plan.value.spec, null, 2), item);
      const generated = this.el('details', undefined, item); this.el('summary', 'Generált HA-konfiguráció', generated);
      this.el('pre', JSON.stringify(plan.value.config, null, 2), generated);
      if (plan.value.status === 'pending') this.button(item, 'Jóváhagyás és mentés kikapcsolva', async () => {
        if (confirm('A megjelenített konfiguráció mentésre kerül a HA-ba, kikapcsolt állapotban. Alkalmazod?')) await this.perform('apply', {plan_id: plan.key});
      });
      if (plan.value.result) this.el('pre', JSON.stringify(plan.value.result, null, 2), item);
    }
    const revisions = this.section('Változások és visszaállítás');
    for (const revision of s.revisions) {
      const r = revision.value; const item = this.el('section', undefined, revisions);
      this.el('h3', `${r.after.alias} · ${r.status}`, item);
      this.el('small', revision.updated_at, item);
      this.el('pre', JSON.stringify({before_spec: r.before_spec, after_spec: r.after_spec}, null, 2), item);
      const details = this.el('details', undefined, item); this.el('summary', 'Előtte / utána', details);
      this.el('pre', JSON.stringify({before: r.before, after: r.after}, null, 2), details);
      if (r.can_enable) this.button(item, 'Ellenőrzött szabály engedélyezése', async () => {
        if (confirm('A szabály a HA-ban bekapcsol, és eseményre működésbe léphet. Engedélyezed?')) await this.perform('enable', {automation_id: r.automation_id, revision_id: revision.key});
      });
      this.button(item, 'E változás visszaállítása', async () => {
        if (confirm('Visszaállítod az előző konfigurációt? Közben kézzel módosított szabályt Ziko nem ír felül.')) await this.perform('rollback', {revision_id: revision.key});
      });
    }
  }
}
if (!customElements.get('ziko-operator-panel')) customElements.define('ziko-operator-panel', ZikoOperatorPanel);
