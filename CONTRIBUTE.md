# Contribute
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

This page serves as a knowledge base for maintaining the code base under this project. This includes front end, both back ends and the simulation core. 

![](frontend/public/docs/Summary_Architecture.png)

## Structure of Front End 
This application uses [App Router](https://nextjs.org/docs/app/getting-started/project-structure) from Next.JS. This defines the folder structure you see in here. 

Under the `app/` folder, there are two folders: `(core)`and `(docs)`. They are the route groups. This dos not change the URL structure, but they are needed because they uses different root providers: The core uses a custom made provider, while the documentations are provided by FumaDocs. 

The `app/ui` folder contains the global CSS definitions. Shall you need to create the styles please put them under the `global.css` file. 

## Simulation Run

```mermaid
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>John: Hello John, how are you?
    loop HealthCheck
        John->>John: Fight against hypochondria
    end
    Note right of John: Rational thoughts <br/>prevail!
    John-->>Alice: Great!
    John->>Bob: How about you?
    Bob-->>John: Jolly good!
```

## Documentation Page (Front End)
The documentations accessed by normal front end UI captures the knowledge base for using the application by normal means. While the markdown files here are meta instructions (e.g. maintain the code base). 

From the front end the URL is `<url>/docs`. For example, in local it is `localhost:3000/docs`

### Add a New Page
You can add a page under `/frontend/content/docs/` or its subfolders. The pages under subfolders will become under different sections in the documentation. 

### Add a New Section
1. Create a new folder under `/frontend/content/docs/`
2. Under the new folder create:
	* `meta.json` which contains the pages required. 
	* Any `.mdx` files
3. At the `meta.json` file of the parent folder, add the folder name as one of the pages. For example 
	```
	{
		"pages": [ "index", "faq", "simulation", "tutorial" ]
	}
	```
	If `"simulation"` is the child folder. 

### Add Images
The images are located from `/public`. Hence when refering them use this as the root folder. For example, documentations are has a path of `/docs/<img-file>`.










## Simulation Inventory Database

There are 2 databases which is used in this solution: 
* Relational database which records the stock of the simulations
* A NoSQL database (probably MongoDB) to store the simulation details or logs (Not implemented)

This section is dedicated to the relational database. 

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    CUSTOMER }|..|{ DELIVERY-ADDRESS : uses
```
