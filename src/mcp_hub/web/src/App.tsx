import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Market from './pages/Market'
import ServerDetail from './pages/ServerDetail'
import MyServers from './pages/MyServers'
import ConfigPage from './pages/ConfigPage'
import Builder from './pages/Builder'
import MyConfig from './pages/MyConfig'
import Login from './pages/Login'
import Publish from './pages/Publish'
import MonitorDashboard from './pages/MonitorDashboard'
import LocalDiscovery from './pages/LocalDiscovery'
import Guide from './pages/Guide'
import ProfilePage from './pages/ProfilePage'
import ComparePage from './pages/ComparePage'
import NotificationsPage from './pages/NotificationsPage'
import PresetMarket from './pages/PresetMarket'
import ReportsPage from './pages/ReportsPage'
import TelemetryPanel from './components/TelemetryPanel'
import AdminLayout from './pages/admin/AdminLayout'
import AdminOverview from './pages/admin/AdminOverview'
import AdminUsers from './pages/admin/AdminUsers'
import AdminUserDetail from './pages/admin/AdminUserDetail'
import AdminServers from './pages/admin/AdminServers'
import AdminServerDetail from './pages/admin/AdminServerDetail'
import AdminAnalytics from './pages/admin/AdminAnalytics'
import AdminValidation from './pages/admin/AdminValidation'
import AdminReviews from './pages/admin/AdminReviews'
import AdminAuditLog from './pages/admin/AdminAuditLog'
import NotFound from './pages/NotFound'

function HubRoutes() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/market" element={<Market />} />
        <Route path="/servers/:id" element={<ServerDetail />} />
        <Route path="/my-servers" element={<MyServers />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/my-config" element={<MyConfig />} />
        <Route path="/builder" element={<Builder />} />
        <Route path="/login" element={<Login />} />
        <Route path="/publish" element={<Publish />} />
        <Route path="/publish/mine" element={<Publish />} />
        <Route path="/monitor" element={<MonitorDashboard />} />
        <Route path="/devices" element={<TelemetryPanel view="devices" />} />
        <Route path="/inventory" element={<LocalDiscovery />} />
        <Route path="/local" element={<Navigate to="/inventory" replace />} />
        <Route path="/analytics" element={<TelemetryPanel view="analytics" />} />
        <Route path="/validation" element={<TelemetryPanel view="validation" />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/guide" element={<Guide />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/alerts" element={<NotificationsPage />} />
        <Route path="/notifications" element={<Navigate to="/alerts" replace />} />
        <Route path="/presets" element={<PresetMarket />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminOverview />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="users/:userId" element={<AdminUserDetail />} />
        <Route path="servers" element={<AdminServers />} />
        <Route path="servers/:serverId" element={<AdminServerDetail />} />
        <Route path="analytics" element={<AdminAnalytics />} />
        <Route path="validation" element={<AdminValidation />} />
        <Route path="reviews" element={<AdminReviews />} />
        <Route path="audit" element={<AdminAuditLog />} />
      </Route>
      <Route path="*" element={<HubRoutes />} />
    </Routes>
  )
}
