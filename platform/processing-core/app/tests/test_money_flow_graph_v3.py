from app.models.money_flow_v3 import MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.services.money_flow.graph import MoneyFlowGraphBuilder


def test_graph_builder_idempotent():
    builder = MoneyFlowGraphBuilder(tenant_id=1, client_id="client-1")
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.SUBSCRIPTION,
        src_id="sub-1",
        link_type=MoneyFlowLinkType.GENERATES,
        dst_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
        dst_id="charge-1",
    )
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.SUBSCRIPTION,
        src_id="sub-1",
        link_type=MoneyFlowLinkType.GENERATES,
        dst_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
        dst_id="charge-1",
    )
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
        src_id="charge-1",
        link_type=MoneyFlowLinkType.GENERATES,
        dst_type=MoneyFlowLinkNodeType.INVOICE,
        dst_id="invoice-1",
    )

    links = builder.build()
    assert len(links) == 2
    assert {link.link_type for link in links} == {MoneyFlowLinkType.GENERATES}
