package com.example.pacs008;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.Callable;
import java.util.stream.Collectors;

/**
 * Runs one call for an input case and prints its actual output as {@code RESULT|<case>|<output>},
 * so the comparator can line up legacy and new-gen outputs for the same input.
 */
public final class Recorder {

    private Recorder() {
    }

    public static String capture(String caseId, Callable<?> call) {
        String output;
        try {
            output = render(call.call());
        } catch (Exception e) {
            output = "throws " + e.getClass().getSimpleName();
        }
        System.out.println("RESULT|" + caseId + "|" + output);
        return output;
    }

    private static String render(Object value) {
        if (value instanceof BigDecimal d) {
            return d.toPlainString();
        }
        if (value instanceof List<?> list) {
            return list.stream().map(String::valueOf).collect(Collectors.joining(";"));
        }
        if (value instanceof Map<?, ?> map) {
            return new TreeMap<>(map).entrySet().stream()
                    .map(e -> e.getKey() + "=" + e.getValue())
                    .collect(Collectors.joining(";"));
        }
        return String.valueOf(value);
    }
}
