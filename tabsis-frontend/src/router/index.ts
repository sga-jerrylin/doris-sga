import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import ProjectHub from '../views/ProjectHub.vue'
import CompanyDashboard from '../views/CompanyDashboard.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            name: 'root',
            component: MainLayout,
            children: [
                {
                    path: '',
                    name: 'home',
                    component: CompanyDashboard
                }
            ]
        },
        {
            path: '/project/:projectId',
            component: MainLayout,
            children: [
                {
                    path: '',
                    name: 'project-dashboard',
                    component: CompanyDashboard
                },

                {
                    path: 'company/:companyId',
                    name: 'company-dashboard',
                    component: CompanyDashboard
                },
                {
                    path: 'company/:companyId/module/invoice',
                    name: 'module-invoice',
                    component: () => import('../views/modules/InvoiceModule.vue')
                },
                {
                    path: 'company/:companyId/module/bank',
                    name: 'module-bank',
                    component: () => import('../views/modules/BankModule.vue')
                }

            ]
        },
        {
            path: '/settings',
            component: MainLayout,
            children: [
                {
                    path: '',
                    name: 'settings',
                    component: () => import('../views/SettingsView.vue')
                }
            ]
        }
    ]
})

export default router
