import { Routes, Route, Link, useLocation } from 'react-router-dom'
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

export default function App() {
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
        <Route path="/local" element={<LocalDiscovery />} />
        <Route path="/guide" element={<Guide />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/presets" element={<PresetMarket />} />
      </Routes>
    </Layout>
  )
}
