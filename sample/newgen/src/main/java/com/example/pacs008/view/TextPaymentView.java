package com.example.pacs008.view;

import com.example.pacs008.model.ValidationError;
import com.example.pacs008.service.ProcessingResult;
import java.util.stream.Collectors;

/**
 * One-line plain-text view, e.g. "ACCEPTED MSG-0001 INSTR-0001 EUR 1000.00 rows=1" or
 * "REJECTED R20 R22 rows=0" (rule codes sorted and de-duplicated).
 */
public class TextPaymentView implements PaymentView {

    @Override
    public String contentType() {
        return "text/plain";
    }

    @Override
    public String render(ProcessingResult result) {
        var outcome = switch (result.status()) {
            case ACCEPTED -> {
                var payment = result.payment();
                yield "ACCEPTED %s %s %s %s".formatted(payment.messageId(), payment.instructionId(),
                        payment.currency(), payment.amount().toPlainString());
            }
            case REJECTED -> result.errors().stream().map(ValidationError::code).distinct().sorted()
                    .collect(Collectors.joining(" ", "REJECTED ", ""));
        };
        return outcome + " rows=" + result.storedRows();
    }
}
