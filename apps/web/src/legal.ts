/** Publisher details shown on the legal pages. Change them here only. */
export const PUBLISHER = "hōnō";
export const CONTACT_EMAIL = "contact@hōnō.com";
export const UPDATED = { fr: "20 novembre 2026", en: "20 November 2026" };

export type Lang = "fr" | "en";
type Section = { title: string; text?: string[]; list?: string[] };
type Doc = { title: string; intro: string; sections: Section[] };

export const TERMS: Record<Lang, Doc> = {
  fr: {
    title: "Conditions d'utilisation",
    intro: `Cadence est un service édité par ${PUBLISHER} qui permet de préparer, planifier et publier du contenu sur des réseaux sociaux. En créant un compte, vous acceptez les présentes conditions.`,
    sections: [
      {
        title: "1. Le service",
        text: [
          "Cadence vous permet de connecter vos comptes de réseaux sociaux, d'importer des médias, de rédiger des publications et de les publier immédiatement ou à une date choisie. Le service peut aussi être piloté par un assistant d'intelligence artificielle que vous autorisez vous-même au moyen d'une clé d'accès.",
        ],
      },
      {
        title: "2. Votre compte",
        text: [
          "Vous devez fournir une adresse e-mail valide et garder votre mot de passe confidentiel. Vous êtes responsable de l'activité réalisée depuis votre compte et avec les clés d'accès que vous créez. Vous pouvez révoquer une clé à tout moment depuis les réglages.",
        ],
      },
      {
        title: "3. Comptes de réseaux sociaux connectés",
        text: [
          "Vous ne devez connecter que des comptes dont vous êtes titulaire ou que vous êtes autorisé à gérer. Cadence agit sur ces comptes uniquement sur vos instructions : il ne publie que les contenus que vous avez créés ou approuvés.",
          "L'utilisation de chaque réseau reste soumise aux conditions de ce réseau (notamment TikTok, Instagram, Facebook, LinkedIn et X). Vous vous engagez à les respecter. Vous pouvez déconnecter un compte à tout moment depuis Cadence ou depuis les réglages du réseau concerné.",
        ],
      },
      {
        title: "4. Vos contenus",
        text: [
          "Vous restez propriétaire des textes, images et vidéos que vous importez. Vous nous accordez uniquement le droit de les stocker et de les transmettre aux réseaux que vous avez choisis, dans le seul but de fournir le service.",
          "Vous garantissez disposer des droits nécessaires sur ces contenus, et vous vous interdisez de publier des contenus illicites, trompeurs, haineux, ou portant atteinte aux droits de tiers.",
        ],
      },
      {
        title: "5. Usages interdits",
        list: [
          "contourner les limites techniques ou les règles des réseaux sociaux ;",
          "diffuser du spam ou automatiser des comportements inauthentiques ;",
          "tenter d'accéder aux données d'autres utilisateurs ;",
          "perturber le fonctionnement du service.",
        ],
      },
      {
        title: "6. Disponibilité",
        text: [
          "Le service est fourni « en l'état ». Nous faisons notre possible pour qu'il fonctionne, mais une publication peut échouer ou être retardée, notamment en cas d'indisponibilité ou de refus d'un réseau social. Cadence vous indique l'état de chaque publication ; il vous appartient de le vérifier pour les contenus importants.",
        ],
      },
      {
        title: "7. Responsabilité",
        text: [
          "Dans les limites permises par la loi, notre responsabilité ne peut être engagée pour les dommages indirects, la perte de données, ou les conséquences d'une décision prise par un réseau social à l'égard de vos comptes ou de vos contenus.",
        ],
      },
      {
        title: "8. Fin du service",
        text: [
          "Vous pouvez cesser d'utiliser Cadence et demander la suppression de votre compte à tout moment. Nous pouvons suspendre un compte en cas de manquement aux présentes conditions.",
        ],
      },
      {
        title: "9. Modifications et droit applicable",
        text: [
          "Nous pouvons faire évoluer ces conditions ; la date de mise à jour figure en haut de cette page. Les présentes conditions sont soumises au droit français.",
        ],
      },
      { title: "10. Contact", text: [`Pour toute question : ${CONTACT_EMAIL}.`] },
    ],
  },
  en: {
    title: "Terms of Service",
    intro: `Cadence is a service published by ${PUBLISHER} that lets you prepare, schedule and publish content on social networks. By creating an account, you accept these terms.`,
    sections: [
      {
        title: "1. The service",
        text: [
          "Cadence lets you connect your social media accounts, upload media, write posts and publish them immediately or at a time you choose. The service can also be operated by an AI assistant that you authorize yourself with an access key.",
        ],
      },
      {
        title: "2. Your account",
        text: [
          "You must provide a valid email address and keep your password confidential. You are responsible for activity carried out from your account and with the access keys you create. You can revoke a key at any time from the settings.",
        ],
      },
      {
        title: "3. Connected social media accounts",
        text: [
          "You may only connect accounts that you own or are authorized to manage. Cadence acts on these accounts only on your instructions: it publishes only content that you created or approved.",
          "Your use of each network remains subject to that network's own terms (including TikTok, Instagram, Facebook, LinkedIn and X), which you agree to follow. You can disconnect an account at any time from Cadence or from the settings of the network concerned.",
        ],
      },
      {
        title: "4. Your content",
        text: [
          "You keep ownership of the text, images and videos you upload. You only grant us the right to store them and to transmit them to the networks you selected, for the sole purpose of providing the service.",
          "You confirm that you hold the necessary rights to this content, and you agree not to publish content that is unlawful, misleading, hateful, or that infringes the rights of others.",
        ],
      },
      {
        title: "5. Prohibited uses",
        list: [
          "circumventing the technical limits or rules of social networks;",
          "sending spam or automating inauthentic behaviour;",
          "attempting to access other users' data;",
          "disrupting the operation of the service.",
        ],
      },
      {
        title: "6. Availability",
        text: [
          "The service is provided “as is”. We do our best to keep it working, but a publication may fail or be delayed, in particular when a social network is unavailable or rejects it. Cadence shows the status of each publication; it is up to you to check it for important content.",
        ],
      },
      {
        title: "7. Liability",
        text: [
          "To the extent permitted by law, we are not liable for indirect damages, loss of data, or the consequences of a decision taken by a social network regarding your accounts or content.",
        ],
      },
      {
        title: "8. Ending the service",
        text: [
          "You can stop using Cadence and request deletion of your account at any time. We may suspend an account that breaches these terms.",
        ],
      },
      {
        title: "9. Changes and governing law",
        text: [
          "We may update these terms; the date of the last update is shown at the top of this page. These terms are governed by French law.",
        ],
      },
      { title: "10. Contact", text: [`For any question: ${CONTACT_EMAIL}.`] },
    ],
  },
};

export const PRIVACY: Record<Lang, Doc> = {
  fr: {
    title: "Politique de confidentialité",
    intro: `Cette page explique quelles données Cadence, édité par ${PUBLISHER}, collecte, pourquoi, et comment vous pouvez les faire supprimer.`,
    sections: [
      {
        title: "1. Données que nous collectons",
        list: [
          "Compte : votre adresse e-mail et votre mot de passe, conservé sous forme hachée (nous ne pouvons pas le lire).",
          "Comptes connectés : pour chaque compte de réseau social que vous connectez, son identifiant, son nom, son nom d'utilisateur, l'adresse de sa photo de profil, et les jetons d'accès délivrés par le réseau. Ces jetons sont chiffrés avant d'être enregistrés. Nous ne recevons jamais le mot de passe de vos comptes de réseaux sociaux.",
          "Contenus : les textes, images et vidéos que vous importez, les dates de planification, et le résultat de chaque publication (statut, lien, message d'erreur éventuel).",
          "Technique : un cookie de session strictement nécessaire à la connexion, et des journaux techniques (adresse IP, date, requête) utilisés pour la sécurité et le dépannage.",
        ],
      },
      {
        title: "2. Pourquoi nous les utilisons",
        text: [
          "Ces données servent uniquement à fournir le service : vous identifier, afficher vos contenus, et publier sur les comptes que vous avez connectés, aux dates que vous avez choisies. Nous ne vendons pas vos données, nous ne les utilisons pas à des fins publicitaires, et nous n'utilisons pas vos contenus pour entraîner des modèles d'intelligence artificielle.",
        ],
      },
      {
        title: "3. Données issues des réseaux sociaux",
        text: [
          "Lorsque vous connectez un compte TikTok, Instagram, Facebook, LinkedIn ou X, nous demandons uniquement les autorisations nécessaires pour identifier ce compte et y publier vos contenus. Nous ne lisons ni vos messages privés, ni vos abonnés, ni vos statistiques.",
          "Les données reçues de ces réseaux ne sont partagées avec aucun tiers, hors les prestataires techniques listés ci-dessous. Lorsque vous publiez, vos contenus sont transmis au réseau concerné, qui les traite selon sa propre politique de confidentialité.",
        ],
      },
      {
        title: "4. Assistant d'intelligence artificielle",
        text: [
          "Si vous créez une clé d'accès et la confiez à un assistant d'IA, cet assistant peut consulter vos comptes connectés et vos publications, et en créer de nouvelles, dans les limites que vous avez fixées. Cet accès n'existe que si vous créez une clé, et cesse dès que vous la révoquez.",
        ],
      },
      {
        title: "5. Prestataires techniques",
        text: ["Le service s'appuie sur des hébergeurs qui traitent les données pour notre compte :"],
        list: [
          "Vercel : hébergement du site ;",
          "Railway : hébergement de l'application ;",
          "Cloudflare (R2) : stockage des images et vidéos ;",
          "un hébergeur de base de données PostgreSQL : stockage des données de compte et des publications.",
        ],
      },
      {
        title: "6. Durée de conservation",
        text: [
          "Vos données sont conservées tant que votre compte existe. Lorsque vous déconnectez un compte de réseau social, ses jetons d'accès sont supprimés immédiatement. Lorsque vous supprimez un média ou une publication, il est retiré de nos systèmes. À la suppression de votre compte, l'ensemble de vos données est effacé sous 30 jours.",
        ],
      },
      {
        title: "7. Vos droits et la suppression de vos données",
        text: [
          `Vous pouvez accéder à vos données, les corriger, les exporter, vous opposer à leur traitement ou en demander la suppression. Pour supprimer votre compte et toutes les données associées, écrivez à ${CONTACT_EMAIL} depuis l'adresse e-mail de votre compte : nous traitons la demande sous 30 jours.`,
          "Vous pouvez aussi retirer à tout moment l'accès de Cadence depuis les réglages de sécurité de chaque réseau social. Si vous résidez dans l'Union européenne, vous pouvez saisir l'autorité de protection des données de votre pays (en France, la CNIL).",
        ],
      },
      {
        title: "8. Sécurité",
        text: [
          "Les échanges sont chiffrés (HTTPS), les mots de passe sont hachés, et les jetons d'accès aux réseaux sociaux sont chiffrés au repos. Aucune mesure n'offre une sécurité absolue ; en cas d'incident affectant vos données, nous vous en informerons.",
        ],
      },
      {
        title: "9. Modifications et contact",
        text: [
          `Nous pouvons mettre à jour cette politique ; la date figure en haut de cette page. Pour toute question : ${CONTACT_EMAIL}.`,
        ],
      },
    ],
  },
  en: {
    title: "Privacy Policy",
    intro: `This page explains what data Cadence, published by ${PUBLISHER}, collects, why, and how you can have it deleted.`,
    sections: [
      {
        title: "1. Data we collect",
        list: [
          "Account: your email address and your password, stored as a hash (we cannot read it).",
          "Connected accounts: for each social media account you connect, its identifier, name, username, profile picture address, and the access tokens issued by the network. These tokens are encrypted before being stored. We never receive the password of your social media accounts.",
          "Content: the text, images and videos you upload, scheduling dates, and the result of each publication (status, link, error message if any).",
          "Technical: a session cookie strictly necessary for signing in, and technical logs (IP address, date, request) used for security and troubleshooting.",
        ],
      },
      {
        title: "2. Why we use it",
        text: [
          "This data is used only to provide the service: to identify you, display your content, and publish to the accounts you connected, at the times you chose. We do not sell your data, we do not use it for advertising, and we do not use your content to train artificial intelligence models.",
        ],
      },
      {
        title: "3. Data from social networks",
        text: [
          "When you connect a TikTok, Instagram, Facebook, LinkedIn or X account, we request only the permissions needed to identify that account and publish your content to it. We do not read your private messages, your followers or your analytics.",
          "Data received from these networks is not shared with any third party, other than the technical providers listed below. When you publish, your content is sent to the network concerned, which processes it under its own privacy policy.",
        ],
      },
      {
        title: "4. AI assistant",
        text: [
          "If you create an access key and give it to an AI assistant, that assistant can view your connected accounts and posts, and create new ones, within the limits you set. This access exists only if you create a key, and ends as soon as you revoke it.",
        ],
      },
      {
        title: "5. Technical providers",
        text: ["The service relies on hosting providers that process data on our behalf:"],
        list: [
          "Vercel: website hosting;",
          "Railway: application hosting;",
          "Cloudflare (R2): storage of images and videos;",
          "a PostgreSQL database host: storage of account data and posts.",
        ],
      },
      {
        title: "6. Retention",
        text: [
          "Your data is kept for as long as your account exists. When you disconnect a social media account, its access tokens are deleted immediately. When you delete a media file or a post, it is removed from our systems. When your account is deleted, all your data is erased within 30 days.",
        ],
      },
      {
        title: "7. Your rights and data deletion",
        text: [
          `You can access your data, correct it, export it, object to its processing or request its deletion. To delete your account and all associated data, write to ${CONTACT_EMAIL} from the email address of your account: we process the request within 30 days.`,
          "You can also withdraw Cadence's access at any time from the security settings of each social network. If you live in the European Union, you may lodge a complaint with the data protection authority of your country (in France, the CNIL).",
        ],
      },
      {
        title: "8. Security",
        text: [
          "Communications are encrypted (HTTPS), passwords are hashed, and social media access tokens are encrypted at rest. No measure offers absolute security; if an incident affects your data, we will inform you.",
        ],
      },
      {
        title: "9. Changes and contact",
        text: [
          `We may update this policy; the date is shown at the top of this page. For any question: ${CONTACT_EMAIL}.`,
        ],
      },
    ],
  },
};
