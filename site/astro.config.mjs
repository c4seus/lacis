import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import starlightLinksValidator from "starlight-links-validator";

export default defineConfig({
    site: "https://c4seus.github.io",
    base: "/lacis",
    trailingSlash: "always",
    integrations: [
        starlight({
            title: "Lacis",
            description:
                "Logiciel libre d'OSINT qui cartographie les entreprises françaises, leurs dirigeants et leurs adresses en un graphe de liens sourcés.",
            locales: {
                root: { label: "Français", lang: "fr" },
            },
            social: [
                { icon: "github", label: "GitHub", href: "https://github.com/c4seus/lacis" },
            ],
            editLink: { baseUrl: "https://github.com/c4seus/lacis/edit/develop/site/" },
            plugins: [starlightLinksValidator()],
        }),
    ],
});
