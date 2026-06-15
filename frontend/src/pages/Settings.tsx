import { Navigate } from "react-router-dom";

/** @deprecated Use /settings/brand */
export default function Settings() {
  return <Navigate to="/settings/brand" replace />;
}
