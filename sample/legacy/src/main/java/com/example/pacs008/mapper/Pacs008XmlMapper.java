package com.example.pacs008.mapper;

import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.AppHeader;
import com.example.pacs008.model.Pacs008Message.Charge;
import com.example.pacs008.model.Pacs008Message.GroupHeader;
import com.example.pacs008.model.Pacs008Message.Party;
import com.example.pacs008.model.Pacs008Message.PostalAddress;
import com.example.pacs008.model.Pacs008Message.Transaction;
import java.io.StringReader;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.ErrorHandler;
import org.xml.sax.InputSource;
import org.xml.sax.SAXParseException;

/**
 * Legacy (Java 8) object mapper: reads a pacs.008.001.08 business message (BusMsg with AppHdr and
 * Document, or a bare Document) into {@link Pacs008Message}. Elements are matched by local name, so
 * the ISO 20022 namespaces may or may not be present.
 */
public class Pacs008XmlMapper {

    private static final ErrorHandler STRICT = new ErrorHandler() {
        @Override
        public void warning(SAXParseException e) {
        }

        @Override
        public void error(SAXParseException e) throws SAXParseException {
            throw e;
        }

        @Override
        public void fatalError(SAXParseException e) throws SAXParseException {
            throw e;
        }
    };

    public Pacs008Message map(String xml) throws MappingException {
        Element root = parse(xml).getDocumentElement();
        Element document = "Document".equals(localName(root)) ? root : child(root, "Document");
        Element transfer = child(document, "FIToFICstmrCdtTrf");
        if (transfer == null) {
            throw new MappingException("Document/FIToFICstmrCdtTrf is missing");
        }
        Pacs008Message message = new Pacs008Message();
        Element appHdr = child(root, "AppHdr");
        if (appHdr != null) {
            message.header = mapHeader(appHdr);
        }
        message.groupHeader = mapGroupHeader(child(transfer, "GrpHdr"));
        for (Element tx : children(transfer, "CdtTrfTxInf")) {
            message.transactions.add(mapTransaction(tx));
        }
        return message;
    }

    private Document parse(String xml) throws MappingException {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            // Payment messages are untrusted input: no DTDs, no external entities.
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            builder.setErrorHandler(STRICT);
            return builder.parse(new InputSource(new StringReader(xml)));
        } catch (Exception e) {
            throw new MappingException("Not a well-formed XML message: " + e.getMessage(), e);
        }
    }

    private AppHeader mapHeader(Element e) {
        AppHeader h = new AppHeader();
        h.fromBic = text(e, "Fr", "FIId", "FinInstnId", "BICFI");
        h.toBic = text(e, "To", "FIId", "FinInstnId", "BICFI");
        h.bizMsgIdr = text(e, "BizMsgIdr");
        h.msgDefIdr = text(e, "MsgDefIdr");
        h.bizSvc = text(e, "BizSvc");
        h.creationDate = text(e, "CreDt");
        return h;
    }

    private GroupHeader mapGroupHeader(Element e) {
        if (e == null) {
            return null;
        }
        GroupHeader g = new GroupHeader();
        g.msgId = text(e, "MsgId");
        g.creationDateTime = text(e, "CreDtTm");
        g.nbOfTxs = text(e, "NbOfTxs");
        g.settlementMethod = text(e, "SttlmInf", "SttlmMtd");
        g.settlementAccount = text(e, "SttlmInf", "SttlmAcct", "Id", "Othr", "Id");
        return g;
    }

    private Transaction mapTransaction(Element e) throws MappingException {
        Transaction t = new Transaction();
        t.instrId = text(e, "PmtId", "InstrId");
        t.endToEndId = text(e, "PmtId", "EndToEndId");
        t.uetr = text(e, "PmtId", "UETR");
        Element amount = child(e, "IntrBkSttlmAmt");
        t.amount = decimal(amount);
        t.currency = attribute(amount, "Ccy");
        t.settlementDate = text(e, "IntrBkSttlmDt");
        t.chargeBearer = text(e, "ChrgBr");
        for (Element c : children(e, "ChrgsInf")) {
            Charge charge = new Charge();
            Element chargeAmount = child(c, "Amt");
            charge.amount = decimal(chargeAmount);
            charge.currency = attribute(chargeAmount, "Ccy");
            charge.agentBic = text(c, "Agt", "FinInstnId", "BICFI");
            t.charges.add(charge);
        }
        t.instructingAgentBic = text(e, "InstgAgt", "FinInstnId", "BICFI");
        t.instructedAgentBic = text(e, "InstdAgt", "FinInstnId", "BICFI");
        t.debtorAgentBic = text(e, "DbtrAgt", "FinInstnId", "BICFI");
        t.creditorAgentBic = text(e, "CdtrAgt", "FinInstnId", "BICFI");
        t.debtor = mapParty(child(e, "Dbtr"));
        t.debtorAccount = mapAccount(child(e, "DbtrAcct"));
        t.creditor = mapParty(child(e, "Cdtr"));
        t.creditorAccount = mapAccount(child(e, "CdtrAcct"));
        for (Element line : children(child(e, "RmtInf"), "Ustrd")) {
            t.unstructuredRemittance.add(line.getTextContent().trim());
        }
        t.relatedRemittance = child(e, "RltdRmtInf") != null;
        return t;
    }

    private Party mapParty(Element e) {
        if (e == null) {
            return null;
        }
        Party p = new Party();
        p.name = text(e, "Nm");
        p.anyBic = text(e, "Id", "OrgId", "AnyBIC");
        Element address = child(e, "PstlAdr");
        if (address != null) {
            PostalAddress a = new PostalAddress();
            a.streetName = text(address, "StrtNm");
            a.buildingNumber = text(address, "BldgNb");
            a.postCode = text(address, "PstCd");
            a.townName = text(address, "TwnNm");
            a.country = text(address, "Ctry");
            for (Element line : children(address, "AdrLine")) {
                a.addressLines.add(line.getTextContent().trim());
            }
            p.address = a;
        }
        return p;
    }

    private String mapAccount(Element e) {
        String iban = text(e, "Id", "IBAN");
        return iban != null ? iban : text(e, "Id", "Othr", "Id");
    }

    private static BigDecimal decimal(Element e) throws MappingException {
        if (e == null) {
            return null;
        }
        String value = e.getTextContent().trim();
        try {
            return new BigDecimal(value);
        } catch (NumberFormatException ex) {
            throw new MappingException("Not a decimal amount: " + value, ex);
        }
    }

    private static String attribute(Element e, String name) {
        if (e == null || !e.hasAttribute(name)) {
            return null;
        }
        return e.getAttribute(name).trim();
    }

    private static String text(Element start, String... path) {
        Element e = start;
        for (String name : path) {
            e = child(e, name);
        }
        if (e == null) {
            return null;
        }
        String value = e.getTextContent().trim();
        return value.isEmpty() ? null : value;
    }

    private static Element child(Element parent, String name) {
        List<Element> found = children(parent, name);
        return found.isEmpty() ? null : found.get(0);
    }

    private static List<Element> children(Element parent, String name) {
        List<Element> result = new ArrayList<Element>();
        if (parent == null) {
            return result;
        }
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element && name.equals(localName(n))) {
                result.add((Element) n);
            }
        }
        return result;
    }

    private static String localName(Node n) {
        return n.getLocalName() != null ? n.getLocalName() : n.getNodeName();
    }
}
