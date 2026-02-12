// frontend/src/ChartDemo.jsx
import { useMemo, useState, useRef, useEffect } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Legend,
  Tooltip,
} from "chart.js";
import api from "./api";
Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Legend, Tooltip);
const API = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
if (!API) throw new Error("VITE_API_BASE is not set");

// Plugin: draw saved and temporary lines from options.plugins.lineDrawer
const lineDrawer = {
  id: "lineDrawer",
  afterDraw: (chart) => {
    try {
      const cfg = chart.options.plugins && chart.options.plugins.lineDrawer;
      if (!cfg) return;
      const lines = cfg.lines || [];
      const temp = cfg.tempLine;

      const ctx = chart.ctx;
      ctx.save();
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";

      const drawOne = (l, color = "rgba(255,200,0,0.9)") => {
        if (!chart.scales || !chart.scales.x || !chart.scales.y) return;
        const x1 = chart.scales.x.getPixelForValue(l.x1);
        const x2 = chart.scales.x.getPixelForValue(l.x2);
        const y1 = chart.scales.y.getPixelForValue(l.y1);
        const y2 = chart.scales.y.getPixelForValue(l.y2);

        if (!isFinite(x1) || !isFinite(x2) || !isFinite(y1) || !isFinite(y2)) return;

        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      };

      lines.forEach((l) => {
        try {
          drawOne(l, "rgba(255,200,0,0.9)");
        } catch (e) {
          // swallow drawing error for individual line
        }
      });

      if (temp) {
        try {
          drawOne(temp, "rgba(255,255,255,0.6)");
        } catch (e) {
          // ignore
        }
      }

      ctx.restore();
    } catch (e) {
      // plugin must not throw — swallow and continue
      // console.error('lineDrawer plugin error', e);
    }
  },
};

Chart.register(lineDrawer);

export default function ChartDemo() {
  // Chart (BTC)
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  // Aktueller Kurs (Name + Preis)
  const [currentPrice, setCurrentPrice] = useState(null);
  const [currentName, setCurrentName] = useState(null);

  // Coins-Tabelle
  const [coins, setCoins] = useState([]);
  const [coinsLoading, setCoinsLoading] = useState(false);
  const [coinsErr, setCoinsErr] = useState(null);

  // Suche / Sortierung
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("market_cap");
  const [sortDir, setSortDir] = useState("desc");

  // Export (Coinbase) + Progress
  const [years, setYears] = useState(10);
  const [exporting, setExporting] = useState(false);
  const [exportErr, setExportErr] = useState(null);
  const [cbStatus, setCbStatus] = useState(null);
  const [chartEnabled, setChartEnabled] = useState(true);
  const [drawingEnabled, setDrawingEnabled] = useState(false);
  const [showMA, setShowMA] = useState(false);
  const [lines, setLines] = useState([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [tempLine, setTempLine] = useState(null);
  const chartRef = useRef(null);
  const startPoint = useRef(null);
  // Filter: Kursbewegung
  const [filterYears, setFilterYears] = useState(3);
  const [filterDirection, setFilterDirection] = useState("gestiegen"); // oder "gefallen"
  const [filterPercent, setFilterPercent] = useState(20);
  // Ergebnis der Filter-Auswertung
  const [filteredResults, setFilteredResults] = useState([]);
  // Tabellen ein/ausblenden
  const [showFilterTable, setShowFilterTable] = useState(false);
  const [showCoinsTable, setShowCoinsTable] = useState(false);
  const [missingSymbols, setMissingSymbols] = useState(new Set());
  // Sparplan
  const [showSavingsSim, setShowSavingsSim] = useState(false);
  const [savingsAmount, setSavingsAmount] = useState(25);
  const [savingsYears, setSavingsYears] = useState(5);
  const [savingsResult, setSavingsResult] = useState("");
  const [savingsCashOnly, setSavingsCashOnly] = useState("");

  //dynamischer Sparplan
  const [dynAmount, setDynAmount] = useState(25);
  const [dynYears, setDynYears] = useState(5);
  const [dynThreshold, setDynThreshold] = useState(5);
  const [dynAdjust, setDynAdjust] = useState(5);
  const [dynMaDays, setDynMaDays] = useState(200);
  const [dynResult, setDynResult] = useState("");
  const [dynCash, setDynCash] = useState("");
  



  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "current_price" || key === "market_cap" ? "desc" : "asc");
    }
  };

  const filteredSortedCoins = useMemo(() => {
    const q = query.trim().toLowerCase();

    const filtered = q
      ? coins.filter((c) => {
          const sym = (c.symbol ?? "").toLowerCase();
          const name = (c.name ?? "").toLowerCase();
          return sym.includes(q) || name.includes(q);
        })
      : coins;

    const dir = sortDir === "asc" ? 1 : -1;

    const getVal = (c) => {
      switch (sortKey) {
        case "symbol":
          return c.symbol ?? "";
        case "name":
          return c.name ?? "";
        case "current_price":
          return c.current_price ?? null;
        case "market_cap":
          return c.market_cap ?? null;
        default:
          return "";
      }
    };

    return [...filtered].sort((a, b) => {
      const av = getVal(a);
      const bv = getVal(b);

      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;

      if (sortKey === "current_price" || sortKey === "market_cap") {
        return (Number(av) - Number(bv)) * dir;
      }

      return String(av).localeCompare(String(bv), "de", { sensitivity: "base" }) * dir;
    });
  }, [coins, query, sortKey, sortDir]);

  const sortIndicator = (key) =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  const usd = (n) =>
    n === null || n === undefined
      ? "-"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          maximumFractionDigits: 2,
        }).format(n);

  const usdCompact = (n) =>
    n === null || n === undefined
      ? "-"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          notation: "compact",
          maximumFractionDigits: 2,
        }).format(n);

  const loadCoins = async () => {
    setCoinsLoading(true);
    setCoinsErr(null);
    try {
      const r = await fetch(`${API}/api/coins?quote=USD&limit=200`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const d = await r.json();
      setCoins(d.coins ?? []);
    } catch (e) {
      setCoinsErr(e.message);
    } finally {
      setCoinsLoading(false);
    }
  };

  // ✅ BTC-Verlauf ins Chart + aktueller Preis als Pegel-Linie
  const loadHistory = async () => {
    setLoading(true);
    setErr(null);
    setShowMA(false);

    try {
      const [histRes, priceRes] = await Promise.all([
        fetch(`${API}/api/btc/history?years=${years}`),
        fetch(`${API}/api/btc/price`),
      ]);

      if (!histRes.ok) throw new Error(`History: ${histRes.status} ${histRes.statusText}`);
      if (!priceRes.ok) throw new Error(`Price: ${priceRes.status} ${priceRes.statusText}`);

      const hist = await histRes.json();
      const price = await priceRes.json();
      setCurrentPrice(Number(price.price_usd));
      setCurrentName("BTC");

      const labels = hist.labels ?? [];
      const data = hist.data ?? [];
      const peg = Number(price.price_usd);
      resetDrawing();

      setChartData({
        labels,
        prices: data,
       
      });
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };
  
  
  // Filer Funktionen
  const applyFilter = async () => {
  try {
    const r = await fetch(`${API}/api/filter/coinbase`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        years: filterYears,
        percent: filterPercent,
        direction: filterDirection,
      }),
    });

    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    setFilteredResults(data.results || []);
  } catch (e) {
    alert("Filter-Fehler: " + e.message);
  }
};

  const resetDrawing = () => {
    setDrawingEnabled(false);
    setLines([]);
    setTempLine(null);
    setShowMA(false);
  };



  // Daten aus CSV Laden für Zeilen Klick
  const loadCsvHistory = async (symbol) => {
    setShowMA(false);

    try {
      const r = await fetch(`${API}/api/csv/history/${symbol}`);
      if (!r.ok) throw new Error("CSV-Fehler");

      const d = await r.json();

      if (!d.available || d.data.length === 0) {
        setMissingSymbols((prev) => new Set(prev).add(symbol));
        return;
      }
      resetDrawing();
      setCurrentName(symbol);
      setMissingSymbols((prev) => {
        const n = new Set(prev);
        n.delete(symbol);
        return n;
      });

      const lastPrice = d.data[d.data.length - 1];

      setCurrentName(symbol);
      setCurrentPrice(lastPrice);

      setChartData({
        labels: d.labels,
        prices: d.data,
        
      });

    } catch (e) {
      setMissingSymbols((prev) => new Set(prev).add(symbol));
    }
  };



  //  Export: NUR Coins, die aktuell in der Tabelle sichtbar sind
  const startCoinbaseExport = async () => {
    setExporting(true);
    setExportErr(null);
    setCbStatus(null);

    try {
      const symbols = filteredSortedCoins.map((c) => c.symbol).filter(Boolean);

      const r = await fetch(`${API}/api/export/coinbase/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols, years }),
      });

      if (!r.ok) throw new Error(await r.text());
      const { job_id } = await r.json();

      const poll = setInterval(async () => {
        try {
          const s = await fetch(`${API}/api/export/coinbase/status/${job_id}`);
          const d = await s.json();
          setCbStatus(d);

          if (d.status === "done" ) {
            clearInterval(poll);
            setExporting(false);
          }
        } catch (e) {
          clearInterval(poll);
          setExportErr(e.message);
          setExporting(false);
        }
      }, 1000);
    } catch (e) {
      setExportErr(e.message);
      setExporting(false);
    }
  };
  const datasets = useMemo(() => {
    if (!chartData) return [];

    const base = [
      {
        label: currentName ?? "Kurs",
        data: chartData.prices,
        borderColor: "#4dabf7",
        backgroundColor: "rgba(77,171,247,0.2)",
        tension: 0.15,
        pointRadius: 0,
        borderWidth: 2,
      },
    ];

    if (showMA) {
      const maValues = calcMovingAverage(chartData.prices, dynMaDays);

      base.push({
        label: `GD (${dynMaDays} Tage)`,
        data: maValues,
        borderColor: "rgba(255,255,255,0.7)",
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.15,
      });
    }

    return base;
  }, [chartData, showMA, dynMaDays, currentName]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        ticks: { color: "#fff", maxTicksLimit: 10 },
        grid: { color: "rgba(255,255,255,0.1)" },
      },
      y: {
        ticks: { color: "#fff" },
        grid: { color: "rgba(255,255,255,0.1)" },
      },
    },
    plugins: {
      legend: { labels: { color: "#fff" } },
      tooltip: { enabled: true },
      lineDrawer: { lines, tempLine },
    },
  }), [lines, tempLine]);

  const runSavingsSimulation = async () => {
    if (!currentName) return;

    const r = await fetch(`${API}/api/simulate/savings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: currentName,
        years: savingsYears,
        monthly_usd: savingsAmount,
      }),
    });

    if (!r.ok) {
      setSavingsResult("Fehler");
      setSavingsCashOnly("");
      return;
    }

    const d = await r.json();

    // 🔹 investiertes Ergebnis (wie bisher)
    setSavingsResult(
      d.result_usd.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " USD"
    );

    // 🔹 NEU: reines Spar-Ergebnis
    const months = Math.round(savingsYears * 12);
    const cashOnly = savingsAmount * months;

    setSavingsCashOnly(
      cashOnly.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " USD"
    );
  };


  const runDynamicSavingsSimulation = async () => {
    if (!currentName) return;

    const r = await fetch(`${API}/api/simulate/savings_dynamic`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: currentName,
        years: dynYears,
        monthly_usd: dynAmount,
        threshold_pct: dynThreshold,
        adjust_pct: dynAdjust,
        ma_days: dynMaDays,
      }),
    });

    const d = await r.json();

    setDynResult(
      d.total_value_usd.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " USD"
    );

    setDynCash(
      d.cash_buffer_usd.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " USD"
    );

  };
  function calcMovingAverage(data, days) {
    if (!days || days <= 1) return [];

    const result = [];

    for (let i = 0; i < data.length; i++) {
      if (i < days - 1) {
        result.push(null);
        continue;
      }

      let sum = 0;
      for (let j = i - days + 1; j <= i; j++) {
        sum += data[j];
      }
      result.push(sum / days);
    }

    return result;
  }



  useEffect(() => {
    // when drawing is disabled or chart data removed, clear any temp drawing
    if (!drawingEnabled || !chartData) {
      setIsDrawing(false);
      startPoint.current = null;
      setTempLine(null);
    }

    // remove all saved lines when drawing is turned off
    if (!drawingEnabled) {
      setLines([]);
    }
  }, [drawingEnabled, chartData]);


//====================================================
// Aufbau UI
//====================================================

  return (
    <div className="chart-card">
      <div className="chart-sticky">
        <div
          className="chart"
          style={{ flex: 1 }}
          onMouseDown={(e) => {
            if (!drawingEnabled || !chartData) return;
            const maybe = chartRef.current;
            const chart = maybe && (maybe.chartInstance ? maybe.chartInstance : maybe);
            if (!chart || !chart.canvas) return;
            try {
              const rect = chart.canvas.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              if (!chart.scales || !chart.scales.x || !chart.scales.y) return;
              const xVal = chart.scales.x.getValueForPixel(x);
              const yVal = chart.scales.y.getValueForPixel(y);
              if (xVal === undefined || yVal === undefined) return;
              startPoint.current = { x: xVal, y: yVal };
              setIsDrawing(true);
            } catch (err) {
              // ignore
            }
          }}
          onMouseMove={(e) => {
            if (!isDrawing || !startPoint.current) return;
            const maybe = chartRef.current;
            const chart = maybe && (maybe.chartInstance ? maybe.chartInstance : maybe);
            if (!chart || !chart.canvas) return;
            try {
              const rect = chart.canvas.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              if (!chart.scales || !chart.scales.x || !chart.scales.y) return;
              const xVal = chart.scales.x.getValueForPixel(x);
              const yVal = chart.scales.y.getValueForPixel(y);
              if (xVal === undefined || yVal === undefined) return;
              const sp = startPoint.current;
              if (!sp) return;
              setTempLine({ x1: sp.x, y1: sp.y, x2: xVal, y2: yVal });
            } catch (err) {
              // ignore
            }
          }}
          onMouseUp={(e) => {
            if (!isDrawing || !startPoint.current) return;
            const maybe = chartRef.current;
            const chart = maybe && (maybe.chartInstance ? maybe.chartInstance : maybe);
            if (!chart || !chart.canvas) return;
            try {
              const rect = chart.canvas.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              if (!chart.scales || !chart.scales.x || !chart.scales.y) return;
              const xVal = chart.scales.x.getValueForPixel(x);
              const yVal = chart.scales.y.getValueForPixel(y);
              if (xVal === undefined || yVal === undefined) {
                startPoint.current = null;
                setIsDrawing(false);
                setTempLine(null);
                return;
              }
              const sp = startPoint.current;
              if (!sp) {
                startPoint.current = null;
                setIsDrawing(false);
                setTempLine(null);
                return;
              }
              setLines((s) => [...s, { x1: sp.x, y1: sp.y, x2: xVal, y2: yVal }]);
            } catch (err) {
              // ignore
            } finally {
              startPoint.current = null;
              setIsDrawing(false);
              setTempLine(null);
            }
          }}
        >
          {chartEnabled ? (
            chartData ? (
              <Line
                ref={chartRef}
                data={{
                  labels: chartData.labels,
                  datasets: datasets,
                }}
                options={options}
              />
            ) : (
              <div className="chart-empty">{loading ? "Lade BTC…" : "Noch keine BTC-Daten geladen"}</div>
            )
          ) : (
            <div className="chart-empty">Diagramm deaktiviert</div>
          )}
        </div>

        <div style={{ width: 160, display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              padding: "8px 10px",
              background: "#111",
              border: "1px solid #333",
              borderRadius: 6,
              color: "#4dabf7",
              fontWeight: 600,
              textAlign: "center",
            }}
          >
            {currentName ?? "Kurs"}
            <div style={{ fontSize: 18, marginTop: 4 }}>
              {currentPrice !== null ? usd(currentPrice) : "–"}
            </div>
          </div>
          <button
            className="btn"
            onClick={() => setDrawingEnabled((s) => !s)}
            disabled={!chartData}
            title={drawingEnabled ? "Zeichnen deaktivieren" : "Zeichnen aktivieren"}
          >
            {drawingEnabled ? "Zeichnen deaktivieren" : "Zeichnen aktivieren"}
          </button>

          <button
            className="btn"
            disabled={!chartData || chartData.length === 0}
            onClick={() => setShowMA(v => !v)}
          >
            {showMA ? "GD ausblenden" : "GD anzeigen"}
          </button>  

          <button
            className="btn"
            onClick={() => setLines([])}
            disabled={lines.length === 0}
            title="Alle gezeichneten Linien löschen"
          >
            Linien löschen
          </button>

        </div>
      </div>


      {/* csv Export   */}
      <div className="panel">
      <div className="panel-title">Aktionen</div>

      <div className="panel-content btn-row">
        <select
          value={years}
          onChange={(e) => setYears(Number(e.target.value))}
          className="select"
        >
          
          <option value={1}>1 Jahr</option>
          <option value={3}>3 Jahre</option>
          <option value={5}>5 Jahre</option>
          <option value={10}>10 Jahre</option>
        </select>

        <button onClick={loadHistory} disabled={loading} className="btn">
          {loading ? "Lade…" : "BTC-Verlauf laden"}
        </button>

        <button onClick={loadCoins} disabled={coinsLoading} className="btn">
          {coinsLoading ? "Lade…" : "Coins (USD) laden"}
        </button>

        <button
          onClick={startCoinbaseExport}
          disabled={exporting || filteredSortedCoins.length === 0}
          className="btn"
        >
        {exporting ? "Export läuft…" : "Coins aus Tabelle → CSV exportieren"}
        </button>
        {exporting && (
          <button
            className="btn"
            onClick={async () => {
              await fetch(`${API}/api/export/coinbase/stop`, { method: "POST" });
            }}
          >
            Export stoppen
          </button>
        )}

      </div>
      </div>
      {/* Fortschritt */}
      {cbStatus && (
        <div style={{ marginTop: 12 }}>
          <div style={{ marginBottom: 6 }}>
            Export: {cbStatus.done}/{cbStatus.total} ({cbStatus.percent}%) – aktuell:{" "}
            {cbStatus.current || "-"} – Fehler: {cbStatus.errors}
          </div>

          <progress value={cbStatus.done || 0} max={cbStatus.total || 1} style={{ width: "100%" }} />

          {cbStatus.status === "done" && (
            <div style={{ marginTop: 6 }}>
              Gespeichert in: <code>backend/exports/{cbStatus.filename}</code>
            </div>
          )}

          {cbStatus.status === "failed" && (
            <div className="error" style={{ marginTop: 6 }}>
              Export failed: {cbStatus.fail_reason}
            </div>
          )}
        </div>
      )}  


      {/* Filter Panel */}
      <div className="panel">
        <div className="panel-title">Filter</div>

        <div className="panel-content">
        <span className="filter-text">Kurse, die in den letzten</span>

        <select
          className="select"
          value={filterYears}
          onChange={(e) => setFilterYears(Number(e.target.value))}
        >
          <option value={0.25}>3 Monate</option>
          <option value={0.5}>6 Monate</option>
          <option value={1}>1 Jahr</option>
          <option value={2}>2 Jahre</option>
          <option value={3}>3 Jahre</option>
          <option value={4}>4 Jahre</option>
          <option value={5}>5 Jahre</option>


        </select>

        <span className="filter-text"> um</span>

        <select
          className="select"
          value={filterPercent}
          onChange={(e) => setFilterPercent(Number(e.target.value))}
        >
          {[2, 5, 10, 20, 30, 40, 50, 75, 100].map((p) => (
            <option key={p} value={p}>
              {p} %
            </option>
          ))}
        </select>

        <select
          className="select"
          value={filterDirection}
          onChange={(e) => setFilterDirection(e.target.value)}
        >
          <option value="gestiegen">gestiegen</option>
          <option value="gefallen">gefallen</option>
        </select>
        
        <span className="filter-text">sind</span>
        <button
          className="btn filter-btn"
          onClick={applyFilter}
        >
          anzeigen
        </button>    
      </div>
      </div>

      {/* Tabelle für Filter-Ergebnisse */}
      <div className="panel panel-table">
        <div className="panel-title">
          <button
            className="panel-toggle"
            onClick={() => setShowFilterTable((s) => !s)}
          >
            {showFilterTable ? "−" : "+"}
          </button>
          Filter-Ergebnis
        </div>

        {showFilterTable && (
          <div className="panel-content">
            {filteredResults.length > 0 ? (
              <div className="table-wrap">
                <table className="coin-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Zeitraum</th>
                      <th>Startpreis</th>
                      <th>Endpreis</th>
                      <th>Änderung</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.map((r) => (
                      <tr
                         key={r.symbol}
                         onClick={() => loadCsvHistory(r.symbol)}
                         style={{
                           cursor: "pointer",
                           color: missingSymbols.has(r.symbol) ? "#ff6b6b" : undefined,
                         }}
                       >
                        <td>
                          {r.symbol}
                          {missingSymbols.has(r.symbol) && " – Verlauf nicht vorhanden"}
                        </td>
                        <td>{r.period}</td>
                        <td>{usd(r.start_price)}</td>
                        <td>{usd(r.end_price)}</td>
                        <td
                          style={{
                            color: r.change_percent >= 0 ? "#51cf66" : "#ff6b6b",
                            fontWeight: 600,
                          }}
                        >
                          {r.change_percent} %
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 14 }}>
                Keine Filter-Ergebnisse – wähle Kriterien und klicke auf „anzeigen“.
              </div>
            )}
          </div>
        )}
      </div>




      {coinsErr && <p className="error">Fehler Coins: {coinsErr}</p>}
      {err && <p className="error">Fehler BTC: {err}</p>}
      {exportErr && <p className="error">Export-Fehler: {exportErr}</p>}

      

      {/* Coins-Tabelle */}
      <div className="panel panel-table">
        <div className="panel-title">
          <button
            className="panel-toggle"
            onClick={() => setShowCoinsTable((s) => !s)}
          >
            {showCoinsTable ? "−" : "+"}
          </button>
          Coin-Übersicht (CoinGecko)
        </div>

        {showCoinsTable && (
          <div className="panel-content">
            {coins.length > 0 ? (
              <>
                <div className="coins-toolbar">
                  <input
                    className="search"
                    placeholder="Suche (Name oder Kürzel)…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />

                  <div className="coins-meta">
                    {filteredSortedCoins.length} / {coins.length}
                  </div>

                  <button className="btn" onClick={() => setQuery("")} disabled={!query}>
                    Clear
                  </button>
                </div>

                <div className="table-wrap">
                  <table className="coin-table">
                    <thead>
                      <tr>
                        <th className="sortable" onClick={() => toggleSort("symbol")}>
                          Kürzel{sortIndicator("symbol")}
                        </th>
                        <th className="sortable" onClick={() => toggleSort("name")}>
                          Name{sortIndicator("name")}
                        </th>
                        <th className="sortable" onClick={() => toggleSort("current_price")}>
                          Preis{sortIndicator("current_price")}
                        </th>
                        <th className="sortable" onClick={() => toggleSort("market_cap")}>
                          Market Cap{sortIndicator("market_cap")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSortedCoins.map((c) => (
                        <tr
                          key={c.id ?? c.symbol}
                          onClick={() => loadCsvHistory(c.symbol)}
                          style={{
                            cursor: "pointer",
                            color: missingSymbols.has(c.symbol) ? "#ff6b6b" : undefined,
                          }}
                        >
                          <td>{c.symbol}{missingSymbols.has(c.symbol) && " – Verlauf nicht vorhanden"}</td>
                          <td>{c.name}</td>
                          <td>{usd(c.current_price)}</td>
                          <td>{usdCompact(c.market_cap)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 14 }}>
                Noch keine Coins geladen.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sparplan Simulation */}
      <div className="panel">
        <div className="panel-title">
          <button
            className="panel-toggle"
            onClick={() => setShowSavingsSim((s) => !s)}
          >
            {showSavingsSim ? "−" : "+"}
          </button>
          Simulation Sparplan
        </div>

        {showSavingsSim && (
          <div className="panel-content">
            <div
              style={{
                width: "100%",
                fontWeight: 600,
                color: "var(--muted)",
                marginBottom: 6,
              }}
            >
            <h3 className="panel-title-small">
              Statischer Sparplan
            </h3>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {/* Sparrate */}
              <select className="select" value={savingsAmount} onChange={(e) => setSavingsAmount(Number(e.target.value))}>
                {[15, 25, 50, 100, 250, 500, 1000].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>

              <span className="filter-text">Dollar</span>

              <span className="filter-text">am 1. des Monats über</span>

              {/* Laufzeit */}
              <select className="select" value={savingsYears} onChange={(e) => setSavingsYears(Number(e.target.value))}>
                {[1, 3, 5, 7, 10].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>

              <span className="filter-text">Jahre investieren</span>

              {/* Aktion */}
              <button
                className="btn"
                onClick={runSavingsSimulation}
                disabled={!currentName}
              >
                Gespartes Kapital errechnen
              </button>

              <span className="filter-text">→</span>

              <input
                className="select"
                style={{ width: 160 }}
                value={savingsResult}
                placeholder="Investiert"
                readOnly
              />

              {savingsCashOnly && (
                <span className="filter-text" style={{ marginLeft: 8 }}>
                  (Bei einfacher Besparung: {savingsCashOnly})
                </span>
              )}


            {/* dynmischer Sparplan */}
         
            <div
              style={{
                width: "100%",
                height: 1,
                background: "var(--border)",
                margin: "12px 0",
              }}
            />

            {/* Dynamischer Sparplan */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  width: "100%",
                  fontWeight: 600,
                  color: "var(--muted)",
                  margin: "8px 0 6px",
                }}
              >
              <h3 className="panel-title-small">
                Dynamischer Sparplan
              </h3>
              </div>


              {/* Betrag */}
              <select
                className="select"
                value={dynAmount}
                onChange={(e) => setDynAmount(Number(e.target.value))}
              >
                {[15, 25, 50, 100, 250, 500, 1000].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              <span className="filter-text">
                Dollar dynamisch am 1. des Monats über
              </span>

              {/* Jahre */}
              <select
                className="select"
                value={dynYears}
                onChange={(e) => setDynYears(Number(e.target.value))}
              >
                {[1, 3, 5, 7, 10].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <span className="filter-text">Jahre investieren.</span>

              {/* Über-/Unterschreitungswert */}
              <select
                className="select"
                value={dynThreshold}
                onChange={(e) => setDynThreshold(Number(e.target.value))}
              >
                {[5, 10, 15, 20, 30, 50].map((p) => (
                  <option key={p} value={p}>{p} %</option>
                ))}
              </select>
              <span className="filter-text">Über/Unterschreitungswert</span>
              
              {/* Gleitender Durchschnitt */}
              <select
                className="select"
                value={dynMaDays}
                onChange={(e) => setDynMaDays(Number(e.target.value))}
              >
                {[10, 30, 100, 200, 500].map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <span className="filter-text">
                Tage gleitender Durchschnitt
              </span>
              {/* Investitionswert */}
              <select
                className="select"
                value={dynAdjust}
                onChange={(e) => setDynAdjust(Number(e.target.value))}
              >
                {[5, 10, 15, 20, 30, 50].map((p) => (
                  <option key={p} value={p}>{p} %</option>
                ))}
              </select>
              <span className="filter-text">Investitionswert</span>

              {/* Aktion */}
              <button
                className="btn"
                onClick={runDynamicSavingsSimulation}
                disabled={!currentName}
              >
                Gespartes Kapital errechnen
              </button>

              <span className="filter-text">→</span>

              <input
                className="select"
                style={{ width: 160 }}
                value={dynResult}
                placeholder="Gesamtwert"
                readOnly
              />

              {dynCash && (
                <span className="filter-text" style={{ marginLeft: 8 }}>
                  (Cash-Puffer: {dynCash})
                </span>
              )}


            </div>
    
            </div>
          </div>
        )}

      </div>
  
    </div>
  );
}
