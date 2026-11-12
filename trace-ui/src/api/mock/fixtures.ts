import type {
  AnomalyExplanation,
  ConfidenceSignals,
  DecisionState,
  EscalationType,
  FlaggedItem,
  Metric,
  Severity,
} from "../types";

export interface CompanyFixture {
  name: string;
  ticker: string;
  cik: string;
  industry: string;
  fiscal_year: number;
  period_end: string;
  filing_url: string;
  metrics: Metric[];
  flaggedItems: FlaggedItem[];
  xbrl: Record<string, number>;
}

function makeSignals(overrides: Partial<ConfidenceSignals> = {}): ConfidenceSignals {
  return {
    snippet_grounding: 0.9,
    concept_match: 0.93,
    unit_consistency: 0.95,
    period_consistency: 0.97,
    prior_year_sanity: 0.9,
    extractor_agreement: 0.9,
    column_period: 0.9,
    cross_statement: 0.9,
    llm_confidence: null,
    ...overrides,
  };
}

interface MetricSeed {
  metric_name: string;
  value_usd: number;
  prior_year_value_usd: number | null;
  confidence: number;
  unit?: string;
  period?: string;
  source_snippet?: string;
  source_header?: string;
  source_row?: string;
  decision_state?: DecisionState;
  severity?: Severity;
  escalation_types?: EscalationType[];
  reasons?: string[];
  rules?: string[];
}

function makeMetric(seed: MetricSeed): Metric {
  const confidenceLabel = seed.confidence >= 0.85 ? "HIGH" : "LOW";
  const compact = seed.value_usd >= 1e9 ? `$${(seed.value_usd / 1e9).toFixed(2)}B` : seed.value_usd >= 1e6 ? `$${(seed.value_usd / 1e6).toFixed(2)}M` : `$${seed.value_usd.toFixed(2)}`;
  return {
    metric_name: seed.metric_name,
    value_usd: seed.value_usd,
    original_value: seed.value_usd,
    unit: seed.unit ?? "USD",
    period: seed.period ?? "FY",
    prior_year_value_usd: seed.prior_year_value_usd,
    confidence: seed.confidence,
    confidence_label: confidenceLabel,
    confidence_signals: makeSignals(),
    source_snippet: seed.source_snippet ?? `${seed.metric_name} from consolidated statements — ${compact}`,
    source_header: seed.source_header ?? "Consolidated Statements",
    source_row: seed.source_row ?? "FY",
    decision_state: seed.decision_state ?? "PENDING",
  };
}

function flag(
  metric: Metric,
  severity: Severity,
  escalationTypes: EscalationType[],
  reasons: string[],
  rules: string[]
): FlaggedItem {
  return { ...metric, reasons, rules, severity, escalation_types: escalationTypes };
}

export const FIXTURES: { companies: CompanyFixture[] } = {
  companies: [
    {
      name: "Apple Inc.",
      ticker: "AAPL",
      cik: "0000320193",
      industry: "Technology",
      fiscal_year: 2025,
      period_end: "2025-09-27",
      filing_url: "https://www.sec.gov/Archives/edgar/data/320193/000032019525000106/aapl-20250928.htm",
      metrics: [
        makeMetric({
          metric_name: "Revenue",
          value_usd: 434600000000,
          prior_year_value_usd: 383300000000,
          confidence: 0.78,
          unit: "USD",
          period: "FY2025",
          source_snippet: "Revenue from Contracts with Customers — $434.60B",
          source_header: "Consolidated Statements",
          source_row: "FY2025",
          decision_state: "FLAGGED",
          severity: "HIGH",
          escalation_types: ["EXTRACTION_RISK"],
          reasons: ["Revenue concept resolved via secondary statement", "Low snippet grounding for revenue recognition boundary"],
          rules: ["CONCEPT_SYNONYM", "SNIPPET_BOUNDARY"],
        }),
        makeMetric({ metric_name: "Net Income", value_usd: 112300000000, prior_year_value_usd: 88700000000, confidence: 0.96, period: "FY2025" }),
        makeMetric({ metric_name: "Total Assets", value_usd: 396400000000, prior_year_value_usd: 365200000000, confidence: 0.93, period: "FY2025" }),
        makeMetric({ metric_name: "Total Liabilities", value_usd: 304400000000, prior_year_value_usd: 283800000000, confidence: 0.9, period: "FY2025" }),
        makeMetric({ metric_name: "Shareholders' Equity", value_usd: 92600000000, prior_year_value_usd: 81000000000, confidence: 0.88, period: "FY2025" }),
        makeMetric({ metric_name: "Operating Cash Flow", value_usd: 118300000000, prior_year_value_usd: 108800000000, confidence: 0.91, period: "FY2025" }),
        makeMetric({ metric_name: "Cash and Cash Equivalents", value_usd: 61100000000, prior_year_value_usd: 55200000000, confidence: 0.89, period: "FY2025" }),
        makeMetric({ metric_name: "Research and Development", value_usd: 31200000000, prior_year_value_usd: 26900000000, confidence: 0.9, period: "FY2025" }),
      ],
      flaggedItems: [
        flag(
          makeMetric({
            metric_name: "Revenue",
            value_usd: 434600000000,
            prior_year_value_usd: 383300000000,
            confidence: 0.78,
            unit: "USD",
            period: "FY2025",
            source_snippet: "Revenue from Contracts with Customers — $434.60B",
            source_header: "Consolidated Statements",
            source_row: "FY2025",
            decision_state: "FLAGGED",
          }),
          "HIGH",
          ["EXTRACTION_RISK"],
          ["Revenue concept resolved via secondary statement", "Low snippet grounding for revenue recognition boundary"],
          ["CONCEPT_SYNONYM", "SNIPPET_BOUNDARY"]
        ),
      ],
      xbrl: {
        Revenue: 436200000000,
        "Net Income": 112800000000,
        "Total Assets": 396400000000,
        "Total Liabilities": 304400000000,
        "Shareholders' Equity": 92600000000,
        "Operating Cash Flow": 118300000000,
        "Cash and Cash Equivalents": 61100000000,
        "Research and Development": 31200000000,
      },
    },
    {
      name: "Microsoft Corporation",
      ticker: "MSFT",
      cik: "0000789019",
      industry: "Technology",
      fiscal_year: 2025,
      period_end: "2025-08-28",
      filing_url: "https://www.sec.gov/Archives/edgar/data/789019/000078901925000106/msft-20250828.htm",
      metrics: [
        makeMetric({ metric_name: "Revenue", value_usd: 254600000000, prior_year_value_usd: 236900000000, confidence: 0.96, period: "FY2025" }),
        makeMetric({ metric_name: "Net Income", value_usd: 102200000000, prior_year_value_usd: 88000000000, confidence: 0.94, period: "FY2025" }),
        makeMetric({ metric_name: "Total Assets", value_usd: 571000000000, prior_year_value_usd: 562000000000, confidence: 0.93, period: "FY2025" }),
        makeMetric({ metric_name: "Total Liabilities", value_usd: 489000000000, prior_year_value_usd: 470000000000, confidence: 0.9, period: "FY2025" }),
        makeMetric({ metric_name: "Shareholders' Equity", value_usd: 82000000000, prior_year_value_usd: 77000000000, confidence: 0.88, period: "FY2025" }),
        makeMetric({ metric_name: "Operating Cash Flow", value_usd: 99800000000, prior_year_value_usd: 94200000000, confidence: 0.9, period: "FY2025" }),
        makeMetric({ metric_name: "Cash and Cash Equivalents", value_usd: 30500000000, prior_year_value_usd: 29500000000, confidence: 0.89, period: "FY2025" }),
        makeMetric({ metric_name: "Research and Development", value_usd: 30000000000, prior_year_value_usd: 28000000000, confidence: 0.95, period: "FY2025" }),
      ],
      flaggedItems: [],
      xbrl: {
        Revenue: 254600000000,
        "Net Income": 102200000000,
        "Total Assets": 571000000000,
        "Total Liabilities": 489000000000,
        "Shareholders' Equity": 82000000000,
        "Operating Cash Flow": 99800000000,
        "Cash and Cash Equivalents": 30500000000,
        "Research and Development": 30000000000,
      },
    },
    {
      name: "NVIDIA Corporation",
      ticker: "NVDA",
      cik: "0001045810",
      industry: "Semiconductors",
      fiscal_year: 2025,
      period_end: "2025-09-28",
      filing_url: "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000106/nvidia-20250928.htm",
      metrics: [
        makeMetric({ metric_name: "Revenue", value_usd: 68000000000, prior_year_value_usd: 60000000000, confidence: 0.97, period: "FY2025" }),
        makeMetric({ metric_name: "Net Income", value_usd: 26700000000, prior_year_value_usd: 19600000000, confidence: 0.98, period: "FY2025" }),
        makeMetric({ metric_name: "Total Assets", value_usd: 104000000000, prior_year_value_usd: 98100000000, confidence: 0.97, period: "FY2025" }),
        makeMetric({ metric_name: "Total Liabilities", value_usd: 33000000000, prior_year_value_usd: 31500000000, confidence: 0.96, period: "FY2025" }),
        makeMetric({ metric_name: "Shareholders' Equity", value_usd: 71000000000, prior_year_value_usd: 67100000000, confidence: 0.97, period: "FY2025" }),
        makeMetric({ metric_name: "Operating Cash Flow", value_usd: 34000000000, prior_year_value_usd: 27700000000, confidence: 0.96, period: "FY2025" }),
        makeMetric({ metric_name: "Cash and Cash Equivalents", value_usd: 34000000000, prior_year_value_usd: 33200000000, confidence: 0.95, period: "FY2025" }),
        makeMetric({ metric_name: "Research and Development", value_usd: 9800000000, prior_year_value_usd: 8000000000, confidence: 0.96, period: "FY2025" }),
      ],
      flaggedItems: [],
      xbrl: {
        Revenue: 68000000000,
        "Net Income": 26700000000,
        "Total Assets": 104000000000,
        "Total Liabilities": 33000000000,
        "Shareholders' Equity": 71000000000,
        "Operating Cash Flow": 34000000000,
        "Cash and Cash Equivalents": 34000000000,
        "Research and Development": 9800000000,
      },
    },
    {
      name: "Tesla, Inc.",
      ticker: "TSLA",
      cik: "0001318609",
      industry: "Consumer Discretionary",
      fiscal_year: 2025,
      period_end: "2025-12-31",
      filing_url: "https://www.sec.gov/Archives/edgar/data/1318609/000131860925000012/tsla-20251231.htm",
      metrics: [
        makeMetric({
          metric_name: "Revenue",
          value_usd: 97000000000,
          prior_year_value_usd: 88000000000,
          confidence: 0.9,
          period: "FY2025",
          decision_state: "FLAGGED",
          severity: "HIGH",
          escalation_types: ["FINANCIAL_ANOMALY"],
          reasons: ["FY2025 revenue increase of 10.2% vs. FY2024 requires manual review", "Delivery-based revenue recognition variance"],
          rules: ["YOY_TOLERANCE", "REVENUE_REC"],
        }),
        makeMetric({ metric_name: "Net Income", value_usd: 18500000000, prior_year_value_usd: 14600000000, confidence: 0.88, period: "FY2025" }),
        makeMetric({ metric_name: "Total Assets", value_usd: 238000000000, prior_year_value_usd: 232000000000, confidence: 0.87, period: "FY2025" }),
        makeMetric({ metric_name: "Total Liabilities", value_usd: 90000000000, prior_year_value_usd: 86000000000, confidence: 0.86, period: "FY2025" }),
        makeMetric({ metric_name: "Shareholders' Equity", value_usd: 148000000000, prior_year_value_usd: 143000000000, confidence: 0.87, period: "FY2025" }),
        makeMetric({ metric_name: "Operating Cash Flow", value_usd: 24500000000, prior_year_value_usd: 21800000000, confidence: 0.87, period: "FY2025" }),
        makeMetric({ metric_name: "Cash and Cash Equivalents", value_usd: 46100000000, prior_year_value_usd: 43900000000, confidence: 0.88, period: "FY2025" }),
        makeMetric({ metric_name: "Research and Development", value_usd: 24500000000, prior_year_value_usd: 22900000000, confidence: 0.88, period: "FY2025" }),
      ],
      flaggedItems: [
        flag(
          makeMetric({
            metric_name: "Revenue",
            value_usd: 97000000000,
            prior_year_value_usd: 88000000000,
            confidence: 0.9,
            period: "FY2025",
            decision_state: "FLAGGED",
          }),
          "HIGH",
          ["FINANCIAL_ANOMALY"],
          ["FY2025 revenue increase of 10.2% vs. FY2024 requires manual review", "Delivery-based revenue recognition variance"],
          ["YOY_TOLERANCE", "REVENUE_REC"]
        ),
      ],
      xbrl: {
        Revenue: 97000000000,
        "Net Income": 18500000000,
        "Total Assets": 238000000000,
        "Total Liabilities": 90000000000,
        "Shareholders' Equity": 148000000000,
        "Operating Cash Flow": 24500000000,
        "Cash and Cash Equivalents": 46100000000,
        "Research and Development": 24500000000,
      },
    },
    {
      name: "Amazon.com, Inc.",
      ticker: "AMZN",
      cik: "0001018724",
      industry: "Consumer Discretionary",
      fiscal_year: 2025,
      period_end: "2025-12-31",
      filing_url: "https://www.sec.gov/Archives/edgar/data/1018724/000101872525000106/amzn-20251231.htm",
      metrics: [
        makeMetric({ metric_name: "Revenue", value_usd: 575000000000, prior_year_value_usd: 574000000000, confidence: 0.95, period: "FY2025" }),
        makeMetric({ metric_name: "Net Income", value_usd: 68000000000, prior_year_value_usd: 59000000000, confidence: 0.93, period: "FY2025" }),
        makeMetric({ metric_name: "Total Assets", value_usd: 780000000000, prior_year_value_usd: 725000000000, confidence: 0.92, period: "FY2025" }),
        makeMetric({ metric_name: "Total Liabilities", value_usd: 660000000000, prior_year_value_usd: 612000000000, confidence: 0.91, period: "FY2025" }),
        makeMetric({ metric_name: "Shareholders' Equity", value_usd: 120000000000, prior_year_value_usd: 113000000000, confidence: 0.9, period: "FY2025" }),
        makeMetric({
          metric_name: "Operating Cash Flow",
          value_usd: 140000000000,
          prior_year_value_usd: 140000000000,
          confidence: 0.72,
          period: "FY2025",
          decision_state: "FLAGGED",
          severity: "MEDIUM",
          escalation_types: ["EXTRACTION_RISK"],
          reasons: ["Cash flow statement row missing operating cash flow line item", "Period-over-period sanity check failed"],
          rules: ["ROW_PRESENCE", "PERIOD_SANITY"],
        }),
        makeMetric({ metric_name: "Cash and Cash Equivalents", value_usd: 105000000000, prior_year_value_usd: 93500000000, confidence: 0.9, period: "FY2025" }),
        makeMetric({ metric_name: "Research and Development", value_usd: 46000000000, prior_year_value_usd: 42000000000, confidence: 0.9, period: "FY2025" }),
      ],
      flaggedItems: [
        flag(
          makeMetric({
            metric_name: "Operating Cash Flow",
            value_usd: 140000000000,
            prior_year_value_usd: 140000000000,
            confidence: 0.72,
            period: "FY2025",
            decision_state: "FLAGGED",
            severity: "MEDIUM",
          }),
          "MEDIUM",
          ["EXTRACTION_RISK"],
          ["Cash flow statement row missing operating cash flow line item", "Period-over-period sanity check failed"],
          ["ROW_PRESENCE", "PERIOD_SANITY"],
        ),
      ],
      xbrl: {
        Revenue: 575000000000,
        "Net Income": 68000000000,
        "Total Assets": 780000000000,
        "Total Liabilities": 660000000000,
        "Shareholders' Equity": 120000000000,
        "Operating Cash Flow": 140000000000,
        "Cash and Cash Equivalents": 105000000000,
        "Research and Development": 46000000000,
      },
    },
  ],
};

export function findCompanyByCik(cik: string): CompanyFixture {
  const clean = cik.replace(/[^0-9]/g, "");
  return FIXTURES.companies.find((c) => c.cik.replace(/[^0-9]/g, "") === clean) ?? FIXTURES.companies[0];
}

export function trueValueFor(company: CompanyFixture, metricName: string): number {
  const key = Object.keys(company.xbrl).find((k) => k.toLowerCase() === metricName.toLowerCase());
  if (key) return company.xbrl[key];
  const fallback = company.metrics.find((m) => m.metric_name.toLowerCase() === metricName.toLowerCase());
  return fallback ? fallback.value_usd : 0;
}

export function flaggedForCompany(cik: string): FlaggedItem[] {
  const company = findCompanyByCik(cik);
  return company.flaggedItems;
}

export function buildAnomalyExplanation(flagged: FlaggedItem): AnomalyExplanation {
  const primary = flagged.escalation_types[0] ?? "EXTRACTION_RISK";
  const detail =
    flagged.reasons[0] ??
    "Flagged by automated validation. Manual review required before release.";
  return {
    metric_name: flagged.metric_name,
    title: `${flagged.metric_name} flagged as ${primary.replace(/_/g, " ")}`,
    detail,
    severity: flagged.severity,
  };
}
