// OPCOM dashboard adapter: read authoritative dated prices, then render ApexCharts.
// No credentials, storage edits, external requests, or equipment actions.
class OpcomPriceBarsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this._key = '';
    this._busy = false;
  }
  setConfig(config) {
    if (![0, 1].includes(config.day_offset ?? 0)) throw new Error('day_offset must be 0 or 1');
    this._config = {...config, entities: {spot: 'sensor.opcom_energy_spot_price', import: 'sensor.opcom_energy_estimated_import_price', last_fetch: 'sensor.opcom_energy_last_successful_fetch', ...config.entities}};
    this._key = '';
    this.shadowRoot.innerHTML = `<style>
      :host{display:block}ha-card{padding:20px 12px 8px;overflow:hidden}
      h2{font-size:20px;font-weight:600;margin:0 10px 4px;color:var(--primary-text-color)}
      .status{font-size:13px;color:var(--secondary-text-color);margin:0 10px 12px;min-height:18px}
      .chart{--ha-card-border-width:0;--ha-card-box-shadow:none;--ha-card-background:transparent;--ha-card-border-radius:0}
      .error{color:var(--error-color)}
    </style><ha-card><h2></h2><div class="status" role="status"></div><div class="chart"></div></ha-card>`;
    this._heading = this.shadowRoot.querySelector('h2');
    this._status = this.shadowRoot.querySelector('.status');
    this._container = this.shadowRoot.querySelector('.chart');
    this._heading.textContent = config.title || (config.day_offset ? 'Mâine' : 'Astăzi');
    this._status.textContent = 'Se încarcă prețurile publicate…';
    this._refresh();
  }
  set hass(value) {
    this._hass = value;
    if (this._chart) this._chart.hass = value;
    this._refresh();
  }
  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._refresh(), 30000);
    this._refresh();
  }
  disconnectedCallback() { clearInterval(this._timer); }
  getCardSize() { return 6; }
  getGridOptions() { return {columns: 36, rows: 'auto', min_columns: 12}; }
  _date(offset, tz) {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
      timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(new Date()).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
    return new Date(Date.UTC(+p.year, +p.month - 1, +p.day + offset)).toISOString().slice(0, 10);
  }
  _midnight(date, tz) {
    const desired = Date.parse(date + 'T00:00:00Z');
    let guess = desired;
    for (let i = 0; i < 3; i++) {
      const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
        timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
      }).formatToParts(new Date(guess)).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
      const shown = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
      guess += desired - shown;
    }
    return guess;
  }
  async _refresh() {
    if (!this._hass || !this._config || !this.isConnected || this._busy) return;
    const tz = this._hass.config.time_zone;
    const date = this._date(this._config.day_offset || 0, tz);
    const key = [date, Math.floor(Date.now() / 300000),
      this._hass.states[this._config.entities.last_fetch]?.state,
      this._hass.states[this._config.entities.import]?.last_updated].join('|');
    if (key === this._key) return;
    this._key = key;
    this._busy = true;
    const config = this._config;
    try {
      const kinds = ['import', 'export', 'spot'];
      const results = await Promise.all(kinds.map(async price_type => {
        const result = await this._hass.callWS({type: 'call_service', domain: 'opcom_energy',
          service: 'get_prices', service_data: {date, price_type}, return_response: true});
        const response = result.response;
        if (!response || !Array.isArray(response.prices)) throw new Error('Răspuns de preț invalid');
        return response;
      }));
      if (this._config !== config || !this.isConnected) return;
      const count = results[2].prices.length;
      const complete = results.every(r => r.complete);
      this._status.classList.remove('error');
      this._status.textContent = `${date} · ${tz} · ${count} intervale · ${complete ? 'Program publicat complet' : 'Date parțiale / în curs de publicare'} · lei/kWh`;
      if (!count) {
        this._container.replaceChildren(); this._chart = null;
        return;
      }
      const next = new Date(Date.parse(date + 'T00:00:00Z') + 86400000).toISOString().slice(0,10);
      const start = this._midnight(date, tz), end = this._midnight(next, tz);
      const localStart = new Date(); localStart.setHours(0, 0, 0, 0);
      const offset = (start - localStart.getTime()) / 60000;
      await customElements.whenDefined('apexcharts-card');
      if (this._config !== config || !this.isConnected) return;
      const chart = document.createElement('apexcharts-card');
      const names = ['Import YellowGrid', 'Export YellowGrid', 'OPCOM angro'];
      const colors = ['#a8dedb', '#50b7ae', '#899ce5'];
      const timeFormat = `EVAL:function(value,timestamp){return new Intl.DateTimeFormat('ro-RO',{timeZone:${JSON.stringify(tz)},hour:'2-digit',minute:'2-digit'}).format(new Date(timestamp));}`;
      chart.setConfig({type: 'custom:apexcharts-card', graph_span: `${(end-start)/3600000}h`,
        span: {start: 'day', offset: `${offset >= 0 ? '+' : ''}${offset}min`},
        header: {show: false}, now: {show: true, label: 'Acum', color: '#999999'},
        apex_config: {chart: {height: 340, toolbar: {show: false}, zoom: {enabled: false}},
          legend: {show: true, position: 'bottom'}, stroke: {curve: 'stepline'},
          plotOptions: {bar: {columnWidth: '85%', borderRadius: 2}}, fill: {opacity: 1},
          xaxis: {type: 'datetime', min: start, max: end, labels: {formatter: timeFormat}},
          tooltip: {shared: true, x: {formatter: `EVAL:function(value){return new Intl.DateTimeFormat('en-GB',{timeZone:${JSON.stringify(tz)},hour:'2-digit',minute:'2-digit'}).format(new Date(value));}`}},
          yaxis: {decimalsInFloat: 2, title: {text: 'lei/kWh'}},
          grid: {borderColor: 'rgba(128,128,128,0.15)'}},
        series: results.map((result, i) => {
          const rows = result.prices.map(r => [Date.parse(r.start), Number.isFinite(r.price) ? r.price : null]);
          const last = result.prices.at(-1);
          if (last && i === 2) rows.push([Date.parse(last.end), Number.isFinite(last.price) ? last.price : null]);
          return {entity: this._config.entities.spot, name: names[i], color: colors[i],
            type: i === 2 ? 'line' : 'column', stroke_width: i === 2 ? 2 : 0, float_precision: 4, extend_to: false,
            show: {legend_value: false, in_header: false}, data_generator: `return ${JSON.stringify(rows)};`};
        })});
      chart.hass = this._hass;
      this._container.replaceChildren(chart); this._chart = chart;
    } catch (error) {
      if (this._config !== config) return;
      this._status.textContent = `Prețuri indisponibile: ${error.message || error}. Reîncercare automată.`;
      this._status.classList.add('error');
      this._container.replaceChildren(); this._chart = null;
    } finally { this._busy = false; }
  }
}
if (!customElements.get('opcom-price-bars-card')) customElements.define('opcom-price-bars-card', OpcomPriceBarsCard);
window.customCards = window.customCards || [];
window.customCards.push({type: 'opcom-price-bars-card', name: 'Prețuri OPCOM și YellowGrid', description: 'Import/export ca bare și OPCOM angro ca linie, astăzi și mâine.'});

