(() => {
  const deck = document.querySelector(".deck");
  if (!deck) return;

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  document.body.classList.add("slide-mode");
  deck.innerHTML = `
    <main class="slides" aria-live="polite">
      <section class="slide active" aria-label="Introduction">
        <div class="slide-inner">
          <div class="brand-lockup">
            <img class="deck-logo" src="grok-logo.png" alt="Grok PM" />
            <div>
              <div class="slide-kicker">Grok PM · Plain-English walkthrough</div>
              <h1>From a world of data to a <span class="accent">15-security portfolio</span></h1>
            </div>
          </div>
          <p class="lead">One click starts an hour-long research process across roughly 500 public companies.</p>
          <div class="headline-numbers">
            <div class="headline-number"><strong>~500</strong><span>companies researched</span></div>
            <div class="headline-number"><strong>~45K</strong><span>financial fields gathered</span></div>
            <div class="headline-number"><strong>~7.5K</strong><span>headlines reviewed</span></div>
            <div class="headline-number"><strong>15</strong><span>final holdings</span></div>
          </div>
          <p class="slide-hint">Click the arrows below, click either side of the slide, or use ← → keys.</p>
        </div>
      </section>

      <section class="slide" aria-label="Pipeline overview">
        <div class="slide-inner">
          <div class="slide-kicker">The journey</div>
          <h2>Five stages. One portfolio.</h2>
          <div class="pipeline-strip">
            <div class="pipeline-node"><span class="icon">📰</span><strong>Gather</strong><small>news + events</small></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-node"><span class="icon">🌎</span><strong>Forecast</strong><small>3-month macro view</small></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-node"><span class="icon">🏢</span><strong>Score</strong><small>~500 companies</small></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-node"><span class="icon">🔽</span><strong>Narrow</strong><small>best ~35</small></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-node"><span class="icon">📊</span><strong>Allocate</strong><small>15 holdings</small></div>
          </div>
          <div class="headline-numbers">
            <div class="headline-number"><strong>~505</strong><span>AI conversations</span></div>
            <div class="headline-number"><strong>8</strong><span>company calls at once</span></div>
            <div class="headline-number"><strong>20–40</strong><span>typical minutes</span></div>
            <div class="headline-number"><strong>few $</strong><span>typical AI cost</span></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Data sources">
        <div class="slide-inner">
          <div class="slide-kicker">Stage 1 · Gather</div>
          <h2>Four sources feed the machine</h2>
          <div class="source-grid">
            <div class="source-card"><span class="source-icon">💹</span><strong>Yahoo Finance</strong><b>~45,000</b><span>financial fields across ~500 companies</span></div>
            <div class="source-card"><span class="source-icon">🗞️</span><strong>Stock News API</strong><b>~7,500</b><span>company headlines + 25 macro articles</span></div>
            <div class="source-card"><span class="source-icon">🌐</span><strong>Wikipedia</strong><b>~3 pages</b><span>current-year and US event context</span></div>
            <div class="source-card"><span class="source-icon">🔎</span><strong>Live web + X</strong><b>up to 10</b><span>fresh search results for the macro report</span></div>
            <div class="source-card"><span class="source-icon">🧠</span><strong>Grok</strong><b>~505 calls</b><span>reads, scores, forecasts, and allocates</span></div>
            <div class="source-card"><span class="source-icon">💾</span><strong>Local checkpoints</strong><b>every firm</b><span>progress survives an interruption</span></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Real company metrics">
        <div class="slide-inner">
          <div class="slide-kicker">Stage 3 · A real company dossier</div>
          <h2>What Grok receives for one stock</h2>
          <div class="stock-header">
            <div class="ticker-badge">AMAT</div>
            <div><h3>Applied Materials, Inc.</h3><p>Semiconductor Equipment &amp; Materials · historical sample from July 2026</p></div>
          </div>
          <div class="metric-grid">
            <div class="metric-card"><div class="metric-label">Market capitalization</div><div class="metric-value">$447.5B</div><div class="metric-note">Company size</div></div>
            <div class="metric-card"><div class="metric-label">Revenue</div><div class="metric-value">$29.0B</div><div class="metric-note">Trailing 12 months</div></div>
            <div class="metric-card"><div class="metric-label">Profit margin</div><div class="metric-value">29.3%</div><div class="metric-note">Profitability</div></div>
            <div class="metric-card"><div class="metric-label">Forward P/E</div><div class="metric-value">34.3×</div><div class="metric-note">Valuation</div></div>
            <div class="metric-card"><div class="metric-label">Revenue growth</div><div class="metric-value">11.4%</div><div class="metric-note">Business momentum</div></div>
            <div class="metric-card"><div class="metric-label">Return on equity</div><div class="metric-value">39.7%</div><div class="metric-note">Capital efficiency</div></div>
            <div class="metric-card"><div class="metric-label">Free cash flow</div><div class="metric-value">$3.04B</div><div class="metric-note">Cash generation</div></div>
            <div class="metric-card"><div class="metric-label">Analyst target</div><div class="metric-value">$586.63</div><div class="metric-note">Consensus view</div></div>
            <div class="metric-card"><div class="metric-label">Total fields</div><div class="metric-value">~90</div><div class="metric-note">For this one firm</div></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Real company headlines">
        <div class="slide-inner">
          <div class="slide-kicker">The same AMAT dossier · News</div>
          <h2>Numbers are paired with recent headlines</h2>
          <div class="headline-grid">
            <div class="headline-card"><div class="source">CNBC</div><p>Chip stocks sell off after Samsung earnings fall short of high AI bar</p><small>July 7, 2026</small></div>
            <div class="headline-card"><div class="source">MarketWatch</div><p>Elon Musk's Terafab could give a major boost to this corner of the chip sector</p><small>July 7, 2026</small></div>
            <div class="headline-card"><div class="source">Zacks</div><p>AMAT Stock Rises 284% From Its 52-Week Low: Should You Buy Now?</p><small>July 7, 2026</small></div>
            <div class="headline-card"><div class="source">Benzinga</div><p>Chip Rout Drags Nasdaq 100 Lower, Oil Climbs: Stock Market Today</p><small>July 7, 2026</small></div>
            <div class="headline-card"><div class="source">Schwab Network</div><p>Tech Corner: AMAT Riding the AI Semiconductor Boom</p><small>July 4, 2026</small></div>
            <div class="headline-card"><div class="source">Seeking Alpha</div><p>Semiconductors Winners And Losers At The Start Of H2 2026</p><small>July 5, 2026</small></div>
          </div>
          <p class="slide-hint">Default: up to 15 headlines per company, filtered toward approved financial outlets.</p>
        </div>
      </section>

      <section class="slide" aria-label="What is sent to Grok">
        <div class="slide-inner">
          <div class="slide-kicker">Input → Grok</div>
          <h2>The app packages evidence into one instruction</h2>
          <div class="input-output">
            <div class="data-stack">
              <div class="data-chip"><b>~90 metrics</b><br>price · valuation · growth · cash · debt · margins</div>
              <div class="data-chip"><b>~15 headlines</b><br>recent events · earnings · analyst views · momentum</div>
              <div class="data-chip"><b>Company identity</b><br>name · ticker · industry · sector</div>
            </div>
            <div>
              <div class="arrow-wide">→</div>
              <div class="grok-core"><img src="grok-logo.png" alt="" /></div>
              <div class="arrow-wide">→</div>
            </div>
            <div class="prompt-box">
              <strong style="color:white">THE INSTRUCTION</strong><br><br>
              Read the latest financial data and headlines.<br><br>
              Write a short investment report covering news, financials, valuation, catalysts, and risks.<br><br>
              Score this firm's stand-alone investment quality from 1 to 100.<br><br>
              <span class="accent">End with: Score: X</span>
            </div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Grok company output">
        <div class="slide-inner">
          <div class="slide-kicker">Grok → Output</div>
          <h2>A dossier becomes a report and a score</h2>
          <div class="score-output">
            <div class="report-snippet">
              <p><b>Recent news</b> · Intense pressure on semiconductor equipment stocks amid a broad chip selloff, balanced by AI-driven DRAM and advanced-packaging demand.</p>
              <p><b>Financials</b> · Revenue of $29.02B, profit margin near 29.3%, and quarterly earnings growth of 31.3% show strong operations.</p>
              <p><b>Valuation</b> · Trailing P/E near 52 and forward P/E near 34 point to a rich price despite strong growth.</p>
              <p><b>Risk</b> · AI spending scrutiny and sector rotation create near-term headwinds.</p>
              <p class="muted">Historical response shortened for presentation.</p>
            </div>
            <div class="score-orb"><span>SCORE</span><strong>52</strong><span>OUT OF 100</span></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Scaling across the market">
        <div class="slide-inner">
          <div class="slide-kicker">Repeat at scale</div>
          <h2>That process happens ~500 times</h2>
          <p class="lead">Eight companies are researched in parallel. Every completed report is saved before the next batch.</p>
          <div class="funnel">
            <div class="f1">~500 S&amp;P 500 companies</div>
            <div class="f2">~500 reports + scores</div>
            <div class="f3">Top 30 by score</div>
            <div class="f4">~35 diversified candidates</div>
          </div>
          <div class="headline-numbers">
            <div class="headline-number"><strong>8×</strong><span>parallel research lanes</span></div>
            <div class="headline-number"><strong>~500</strong><span>saved firm reports</span></div>
            <div class="headline-number"><strong>5</strong><span>soft cap per sector</span></div>
            <div class="headline-number"><strong>0</strong><span>AI calls for the sorting step</span></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Final portfolio">
        <div class="slide-inner">
          <div class="slide-kicker">Final input → Final output</div>
          <h2>Macro forecast + best firms → 15 holdings</h2>
          <table class="mini-portfolio" aria-label="Sample portfolio holdings">
            <thead><tr><th>Weight</th><th>Holding</th><th>Type</th><th>Why it earned a place</th></tr></thead>
            <tbody>
              <tr><td>8% <div class="weight-track"><i style="width:80%"></i></div></td><td><strong>TJX</strong></td><td>Stock</td><td>Off-price retail resilience</td></tr>
              <tr><td>8% <div class="weight-track"><i style="width:80%"></i></div></td><td><strong>XLU</strong></td><td>ETF</td><td>Defensive utilities + data-center demand</td></tr>
              <tr><td>7% <div class="weight-track"><i style="width:70%"></i></div></td><td><strong>XLV</strong></td><td>ETF</td><td>Broad healthcare stability</td></tr>
              <tr><td>7% <div class="weight-track"><i style="width:70%"></i></div></td><td><strong>LLY</strong></td><td>Stock</td><td>GLP-1 momentum and pipeline</td></tr>
              <tr><td>7% <div class="weight-track"><i style="width:70%"></i></div></td><td><strong>ITA</strong></td><td>ETF</td><td>Defense backlog and spending</td></tr>
              <tr><td colspan="4" style="text-align:center;color:var(--muted)">+ 10 more holdings · each with thesis, edge, and risk · weights total 100%</td></tr>
            </tbody>
          </table>
          <p class="slide-hint">Historical sample. The portfolio is research output, not an automatic trade.</p>
        </div>
      </section>

      <section class="slide" aria-label="Time and cost">
        <div class="slide-inner">
          <div class="slide-kicker">The investment behind the answer</div>
          <h2>Most of the hour is spent reading companies</h2>
          <div class="timeline">
            <div class="timeline-item"><div class="timeline-bar" style="height:42px"></div><span>Gather macro data<br>seconds</span></div>
            <div class="timeline-item"><div class="timeline-bar" style="height:68px"></div><span>Macro report<br>~1–2 min</span></div>
            <div class="timeline-item"><div class="timeline-bar"></div><span>Score ~500 firms<br>most of 20–40 min</span></div>
            <div class="timeline-item"><div class="timeline-bar" style="height:30px"></div><span>Sort candidates<br>instant</span></div>
            <div class="timeline-item"><div class="timeline-bar" style="height:68px"></div><span>Build portfolio<br>~1–2 min</span></div>
          </div>
          <div class="headline-numbers">
            <div class="headline-number"><strong>~505</strong><span>Grok calls</span></div>
            <div class="headline-number"><strong>~501</strong><span>Stock News requests</span></div>
            <div class="headline-number"><strong>few $</strong><span>typical AI usage</span></div>
            <div class="headline-number"><strong>1 call</strong><span>to rerun portfolio only</span></div>
          </div>
        </div>
      </section>

      <section class="slide" aria-label="Summary">
        <div class="slide-inner">
          <div class="brand-lockup">
            <img class="deck-logo" src="grok-logo.png" alt="Grok PM" />
            <div>
              <div class="slide-kicker">The takeaway</div>
              <h2>A small output backed by a <span class="accent">large research process</span></h2>
            </div>
          </div>
          <div class="output-grid">
            <div class="visual-card"><strong>45,000+ numbers</strong><span>Financial strength, valuation, growth, cash, debt, and momentum.</span></div>
            <div class="visual-card"><strong>7,500+ headlines</strong><span>Company events and market context from financial outlets.</span></div>
            <div class="visual-card"><strong>~500 written reports</strong><span>One reasoned assessment for nearly every S&amp;P 500 company.</span></div>
            <div class="visual-card"><strong>One macro forecast</strong><span>A shared view of rates, inflation, tariffs, politics, and markets.</span></div>
            <div class="visual-card"><strong>One saved audit trail</strong><span>Every input, score, report, cost, and final portfolio is stored locally.</span></div>
            <div class="visual-card"><strong>15 final decisions</strong><span>A monthly portfolio with weight, thesis, edge, and risk.</span></div>
          </div>
        </div>
      </section>
    </main>

    <div class="slide-controls" aria-label="Slide controls">
      <button type="button" data-prev aria-label="Previous slide">←</button>
      <span class="slide-counter">1 / 11</span>
      <button type="button" data-next aria-label="Next slide">→</button>
    </div>
    <div class="slide-progress" aria-hidden="true"></div>
  `;

  const slides = [...document.querySelectorAll(".slide")];
  const counter = document.querySelector(".slide-counter");
  const progress = document.querySelector(".slide-progress");
  let index = 0;

  function show(next) {
    const target = Math.max(0, Math.min(slides.length - 1, next));
    if (target === index) return;
    slides[index].classList.remove("active");
    slides[index].classList.toggle("exit-left", target > index);
    index = target;
    slides[index].classList.remove("exit-left");
    slides[index].classList.add("active");
    slides[index].scrollTop = 0;
    counter.textContent = `${index + 1} / ${slides.length}`;
    progress.style.width = `${((index + 1) / slides.length) * 100}%`;
    history.replaceState(null, "", `#slide-${index + 1}`);
  }

  document.querySelector("[data-prev]").addEventListener("click", () => show(index - 1));
  document.querySelector("[data-next]").addEventListener("click", () => show(index + 1));
  document.addEventListener("keydown", (event) => {
    if (["ArrowRight", "PageDown", " "].includes(event.key)) {
      event.preventDefault();
      show(index + 1);
    } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
      event.preventDefault();
      show(index - 1);
    } else if (event.key === "Home") show(0);
    else if (event.key === "End") show(slides.length - 1);
  });
  document.querySelector(".slides").addEventListener("click", (event) => {
    if (event.target.closest("a, button, table")) return;
    show(event.clientX < innerWidth / 2 ? index - 1 : index + 1);
  });

  const requested = Number(location.hash.replace("#slide-", "")) - 1;
  progress.style.width = `${100 / slides.length}%`;
  if (Number.isInteger(requested) && requested > 0) show(requested);
  requestAnimationFrame(() => {
    slides.forEach((slide) => { slide.scrollTop = 0; });
  });
})();
