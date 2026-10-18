package com.example.pacs008.view;

import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.ValidationError;
import com.example.pacs008.service.ProcessingResult;
import java.util.TreeSet;

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
        StringBuilder sb = new StringBuilder(result.getStatus().name());
        if (result.getStatus() == ProcessingResult.Status.ACCEPTED) {
            CreditTransferDto payment = result.getPayment();
            sb.append(' ').append(payment.getMessageId())
              .append(' ').append(payment.getInstructionId())
              .append(' ').append(payment.getCurrency())
              .append(' ').append(payment.getAmount().toPlainString());
        } else {
            TreeSet<String> codes = new TreeSet<String>();
            for (ValidationError error : result.getErrors()) {
                codes.add(error.getCode());
            }
            for (String code : codes) {
                sb.append(' ').append(code);
            }
        }
        return sb.append(" rows=").append(result.getStoredRows()).toString();
    }
}
