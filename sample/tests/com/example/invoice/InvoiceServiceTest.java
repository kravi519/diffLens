package com.example.invoice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Shared test suite. Written in Java 8 syntax so it compiles against both
 * the legacy and the new-gen implementation.
 */
class InvoiceServiceTest {

    private final InvoiceService service = new InvoiceService();

    private List<LineItem> sampleItems() {
        return Arrays.asList(
                new LineItem("Keyboard", 2, new BigDecimal("49.99")),
                new LineItem("Mouse", 3, new BigDecimal("19.50")),
                new LineItem("Monitor", 1, new BigDecimal("229.00")));
    }

    @Test
    @DisplayName("Subtotal sums all line totals")
    void subtotalSumsLines() {
        assertEquals(new BigDecimal("387.48"), service.subtotal(sampleItems()));
    }

    @Test
    void subtotalOfEmptyInvoiceIsZero() {
        assertEquals(0, BigDecimal.ZERO.compareTo(service.subtotal(Arrays.<LineItem>asList())));
    }

    @Test
    void discountOfTenPercent() {
        assertEquals(new BigDecimal("90.00"), service.applyDiscount(new BigDecimal("100.00"), 10));
    }

    @Test
    @DisplayName("Discount rounds half up at the cent boundary")
    void discountRoundsHalfUp() {
        assertEquals(new BigDecimal("5.13"), service.applyDiscount(new BigDecimal("10.25"), 50));
    }

    @Test
    void discountRejectsInvalidPercent() {
        assertThrows(IllegalArgumentException.class, () -> service.applyDiscount(BigDecimal.TEN, 120));
    }

    @Test
    void taxIsEighteenPercent() {
        assertEquals(new BigDecimal("18.00"), service.tax(new BigDecimal("100.00")));
    }

    @Test
    void displayNameWithFirstAndLast() {
        assertEquals("DOE, Jane", service.customerDisplayName("Jane", "Doe"));
    }

    @Test
    @DisplayName("Display name without a first name shows only the last name")
    void displayNameWithoutFirstName() {
        assertEquals("DOE", service.customerDisplayName(null, "Doe"));
    }

    @Test
    void topTwoProducts() {
        assertEquals(Arrays.asList("Monitor", "Keyboard"), service.topProducts(sampleItems(), 2));
    }

    @Test
    @DisplayName("Asking for more top products than exist returns all of them")
    void topProductsMoreThanAvailable() {
        assertEquals(3, service.topProducts(sampleItems(), 5).size());
    }

    @Test
    void quantityIsAggregatedPerProduct() {
        List<LineItem> items = Arrays.asList(
                new LineItem("Pen", 2, BigDecimal.ONE),
                new LineItem("Pen", 5, BigDecimal.ONE),
                new LineItem("Pad", 1, BigDecimal.ONE));
        Map<String, Integer> totals = service.quantityByProduct(items);
        assertEquals(Integer.valueOf(7), totals.get("Pen"));
        assertEquals(Integer.valueOf(1), totals.get("Pad"));
    }

    @Test
    @Disabled("Currency conversion not implemented in either version yet")
    void currencyConversion() {
    }
}
