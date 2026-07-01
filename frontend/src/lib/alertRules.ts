import type { SourceDescriptor } from "../api/client";
import type { AlertRule } from "./userData";

export interface AlertEvaluation {
  ruleId: string;
  triggered: boolean;
  message: string;
  disabledReason?: string;
}

export interface AlertEvaluationContext {
  userLocation: { lat: number; lon: number } | null;
  nearbyWarningCount: number;
  maxNearbyWarningLevel: number | null;
  stationMetricValue: number | null;
  staleSourceKeys: string[];
}

export function evaluateAlertRule(rule: AlertRule, context: AlertEvaluationContext): AlertEvaluation {
  if (!rule.enabled) {
    return {
      ruleId: rule.id,
      triggered: false,
      message: rule.name,
      disabledReason: "Reguła wyłączona",
    };
  }

  switch (rule.type) {
    case "warning_nearby": {
      if (!context.userLocation) {
        return {
          ruleId: rule.id,
          triggered: false,
          message: rule.name,
          disabledReason: "Brak zapisanej lokalizacji użytkownika",
        };
      }
      const triggered = context.nearbyWarningCount > 0;
      return {
        ruleId: rule.id,
        triggered,
        message: triggered
          ? `${rule.name}: ${context.nearbyWarningCount} aktywne ostrzeżenia w pobliżu`
          : `${rule.name}: brak aktywnych ostrzeżeń w pobliżu`,
      };
    }
    case "warning_level": {
      const level = rule.warningLevel ?? 1;
      const triggered =
        context.maxNearbyWarningLevel !== null && context.maxNearbyWarningLevel >= level;
      return {
        ruleId: rule.id,
        triggered,
        message: triggered
          ? `${rule.name}: wykryto ostrzeżenie co najmniej poziomu ${level}`
          : `${rule.name}: brak ostrzeżeń poziomu ${level}+`,
      };
    }
    case "station_threshold": {
      if (context.stationMetricValue === null) {
        return {
          ruleId: rule.id,
          triggered: false,
          message: rule.name,
          disabledReason: "Brak wartości pomiaru dla wybranej stacji",
        };
      }
      const threshold = rule.threshold ?? 0;
      const triggered =
        rule.operator === "lt"
          ? context.stationMetricValue < threshold
          : context.stationMetricValue > threshold;
      return {
        ruleId: rule.id,
        triggered,
        message: triggered
          ? `${rule.name}: ${context.stationMetricValue} spełnia próg`
          : `${rule.name}: ${context.stationMetricValue} nie spełnia progu`,
      };
    }
    case "stale_source": {
      const sourceKey = rule.sourceKey ?? "";
      const triggered = context.staleSourceKeys.includes(sourceKey);
      return {
        ruleId: rule.id,
        triggered,
        message: triggered
          ? `${rule.name}: cache źródła ${sourceKey} jest przestarzały lub pusty`
          : `${rule.name}: cache źródła ${sourceKey} wygląda na aktualny`,
      };
    }
    default:
      return {
        ruleId: rule.id,
        triggered: false,
        message: rule.name,
        disabledReason: "Nieobsługiwany typ reguły",
      };
  }
}

export function staleSourceKeys(sources: SourceDescriptor[]): string[] {
  return sources
    .filter((source) => source.cache_status !== "fresh")
    .map((source) => source.key);
}
