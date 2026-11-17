import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import starlightLinksValidator from "starlight-links-validator";

const sharingImage = "https://c4seus.github.io/lacis/sharing-image.png";
const goatCounterCode = process.env.GOATCOUNTER_CODE;
const audienceMeasurement = goatCounterCode
    ? [
          {
              tag: "script",
              attrs: {
                  "data-goatcounter": `https://${goatCounterCode}.goatcounter.com/count`,
                  async: true,
                  src: "https://gc.zgo.at/count.v5.js",
                  crossorigin: "anonymous",
                  integrity:
                      "sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ",
              },
          },
      ]
    : [];

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
            components: { Footer: "./src/components/Footer.astro" },
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
                ...audienceMeasurement,
            ],
            sidebar: [
                {
                    label: "Guide de l'utilisateur",
                    items: [
                        "guide",
                        {
                            label: "Prise en main",
                            items: ["guide/installation", "guide/demonstration", "guide/premiere-enquete"],
                        },
                        {
                            label: "Fonctionnalités",
                            items: [
                                "guide/recherche",
                                "guide/extension",
                                "guide/annonces-bodacc",
                                "guide/homonymes",
                                "guide/entites-etrangeres",
                                "guide/signaux",
                                "guide/preuves",
                                "guide/raccourcis-clavier",
                            ],
                        },
                        {
                            label: "Données et aide",
                            items: [
                                "guide/donnees",
                                "guide/usage-responsable",
                                "guide/depannage",
                                "guide/contribuer",
                                "confidentialite",
                            ],
                        },
                    ],
                },
            ],
            plugins: [starlightLinksValidator()],
        }),
    ],
});
