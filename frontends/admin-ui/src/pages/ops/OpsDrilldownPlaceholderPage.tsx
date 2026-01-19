import React from "react";
import { useLocation } from "react-router-dom";

const useQueryTitle = () => {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  return params.get("title") ?? "Ops drilldown";
};

export const OpsDrilldownPlaceholderPage: React.FC = () => {
  const title = useQueryTitle();

  return (
    <div>
      <h1>{title}</h1>
      <p>Drilldown details are coming in a future sprint.</p>
    </div>
  );
};

export default OpsDrilldownPlaceholderPage;
