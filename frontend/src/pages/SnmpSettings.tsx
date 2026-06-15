import { Navigate } from "react-router-dom";
import SnmpSettingsPanel from "../components/SnmpSettingsPanel";

/** @deprecated Use /settings/snmp */
export default function SnmpSettingsPage() {
  return <Navigate to="/settings/snmp" replace />;
}

export { SnmpSettingsPanel };
