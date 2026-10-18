package com.example.invoice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.api.Test;

class ShippingTest {

    private final InvoiceService service = new InvoiceService();

    @ParameterizedTest(name = "{0} costs {1}")
    @CsvSource({"DOMESTIC, 5.00", "EU, 15.00", "INTL, 30.00"})
    void shippingCostPerRegion(String region, String expected) {
        assertEquals(new BigDecimal(expected), service.shippingCost(region));
    }

    @Test
    void unknownRegionIsRejected() {
        assertThrows(IllegalArgumentException.class, () -> service.shippingCost("MARS"));
    }
}
