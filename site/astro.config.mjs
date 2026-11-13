import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import starlightLinksValidator from "starlight-links-validator";

const sharingImage = "https://c4seus.github.io/lacis/sharing-image.png";

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
            customCss: ["./src/styles/custom.css"],
            head: [
                { tag: "meta", attrs: { property: "og:image", content: sharingImage } },
                { tag: "meta", attrs: { property: "og:image:width", content: "1200" } },
                { tag: "meta", attrs: { property: "og:image:height", content: "630" } },
                {
                    tag: "meta",
                    attrs: {
                        property: "og:image:alt",
                        content: "Lacis, logiciel libre d'OSINT, et sa fenêtre d'enquête",
                    },
                },
            ],
            sidebar: [
                { label: "Guide de l'utilisateur", items: [{ autogenerate: { directory: "guide" } }] },
            ],
            plugins: [starlightLinksValidator()],
        }),
    ],
});
