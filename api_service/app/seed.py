"""
Seed script — populates the database with sample books, users, and interactions for demo.
Run: python -m app.seed
"""

from __future__ import annotations

import asyncio
import random

from sqlalchemy import select

from app.auth.password import hash_password
from app.database import Base, async_session, engine
from app.models.book import Book
from app.models.interaction import InteractionType, UserBookInteraction
from app.models.user import User, UserRole

SAMPLE_BOOKS = [
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "genre": "Classic",
        "description": "A story of the mysteriously wealthy Jay Gatsby and his love for Daisy Buchanan.",
        "isbn": "978-0743273565",
        "published_year": 1925,
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "genre": "Classic",
        "description": "The unforgettable novel of a childhood in a sleepy Southern town.",
        "isbn": "978-0061120084",
        "published_year": 1960,
    },
    {
        "title": "1984",
        "author": "George Orwell",
        "genre": "Dystopian",
        "description": "A dystopian masterpiece about totalitarianism.",
        "isbn": "978-0451524935",
        "published_year": 1949,
    },
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "genre": "Romance",
        "description": "The turbulent relationship between Elizabeth Bennet and Mr. Darcy.",
        "isbn": "978-0141439518",
        "published_year": 1813,
    },
    {
        "title": "The Catcher in the Rye",
        "author": "J.D. Salinger",
        "genre": "Classic",
        "description": "The experiences of young Holden Caulfield.",
        "isbn": "978-0316769488",
        "published_year": 1951,
    },
    {
        "title": "Brave New World",
        "author": "Aldous Huxley",
        "genre": "Dystopian",
        "description": "A futuristic World State of genetically modified citizens.",
        "isbn": "978-0060850524",
        "published_year": 1932,
    },
    {
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "genre": "Fantasy",
        "description": "Bilbo Baggins embarks on an unexpected journey.",
        "isbn": "978-0547928227",
        "published_year": 1937,
    },
    {
        "title": "Harry Potter and the Sorcerer's Stone",
        "author": "J.K. Rowling",
        "genre": "Fantasy",
        "description": "A boy discovers he is a wizard.",
        "isbn": "978-0590353427",
        "published_year": 1997,
    },
    {
        "title": "The Lord of the Rings",
        "author": "J.R.R. Tolkien",
        "genre": "Fantasy",
        "description": "An epic high-fantasy novel.",
        "isbn": "978-0618640157",
        "published_year": 1954,
    },
    {
        "title": "Dune",
        "author": "Frank Herbert",
        "genre": "Science Fiction",
        "description": "Set in the distant future amidst interstellar politics.",
        "isbn": "978-0441013593",
        "published_year": 1965,
    },
    {
        "title": "Foundation",
        "author": "Isaac Asimov",
        "genre": "Science Fiction",
        "description": "The collapse of a Galactic Empire and the birth of a new society.",
        "isbn": "978-0553293357",
        "published_year": 1951,
    },
    {
        "title": "Neuromancer",
        "author": "William Gibson",
        "genre": "Science Fiction",
        "description": "A washed-up computer hacker is hired for the ultimate hack.",
        "isbn": "978-0441569595",
        "published_year": 1984,
    },
    {
        "title": "The Da Vinci Code",
        "author": "Dan Brown",
        "genre": "Thriller",
        "description": "A murder inside the Louvre reveals a battle between the Priory of Sion and Opus Dei.",
        "isbn": "978-0307474278",
        "published_year": 2003,
    },
    {
        "title": "Gone Girl",
        "author": "Gillian Flynn",
        "genre": "Thriller",
        "description": "A woman's disappearance spins an intricate web of lies.",
        "isbn": "978-0307588371",
        "published_year": 2012,
    },
    {
        "title": "The Girl with the Dragon Tattoo",
        "author": "Stieg Larsson",
        "genre": "Thriller",
        "description": "A journalist and hacker investigate a decades-old disappearance.",
        "isbn": "978-0307454546",
        "published_year": 2005,
    },
    {
        "title": "Sapiens",
        "author": "Yuval Noah Harari",
        "genre": "Non-Fiction",
        "description": "A brief history of humankind.",
        "isbn": "978-0062316097",
        "published_year": 2011,
    },
    {
        "title": "Thinking, Fast and Slow",
        "author": "Daniel Kahneman",
        "genre": "Non-Fiction",
        "description": "Exploration of the two systems that drive the way we think.",
        "isbn": "978-0374533557",
        "published_year": 2011,
    },
    {
        "title": "Educated",
        "author": "Tara Westover",
        "genre": "Memoir",
        "description": "A memoir about growing up in a survivalist family.",
        "isbn": "978-0399590504",
        "published_year": 2018,
    },
    {
        "title": "Becoming",
        "author": "Michelle Obama",
        "genre": "Memoir",
        "description": "An intimate memoir by the former First Lady.",
        "isbn": "978-1524763138",
        "published_year": 2018,
    },
    {
        "title": "The Alchemist",
        "author": "Paulo Coelho",
        "genre": "Fiction",
        "description": "A shepherd's journey to find treasure in Egypt.",
        "isbn": "978-0062315007",
        "published_year": 1988,
    },
    {
        "title": "Crime and Punishment",
        "author": "Fyodor Dostoevsky",
        "genre": "Classic",
        "description": "The mental anguish of a poor ex-student who commits murder.",
        "isbn": "978-0486415871",
        "published_year": 1866,
    },
    {
        "title": "The Road",
        "author": "Cormac McCarthy",
        "genre": "Post-Apocalyptic",
        "description": "A father and son walk through a burned America.",
        "isbn": "978-0307387899",
        "published_year": 2006,
    },
    {
        "title": "Ender's Game",
        "author": "Orson Scott Card",
        "genre": "Science Fiction",
        "description": "Children are trained for an alien war.",
        "isbn": "978-0812550702",
        "published_year": 1985,
    },
    {
        "title": "The Martian",
        "author": "Andy Weir",
        "genre": "Science Fiction",
        "description": "An astronaut stranded on Mars must survive.",
        "isbn": "978-0553418026",
        "published_year": 2011,
    },
    {
        "title": "The Name of the Wind",
        "author": "Patrick Rothfuss",
        "genre": "Fantasy",
        "description": "The story of Kvothe, a legendary figure.",
        "isbn": "978-0756404741",
        "published_year": 2007,
    },
    {
        "title": "A Game of Thrones",
        "author": "George R.R. Martin",
        "genre": "Fantasy",
        "description": "Noble families fight for the Iron Throne.",
        "isbn": "978-0553593716",
        "published_year": 1996,
    },
    {
        "title": "The Hunger Games",
        "author": "Suzanne Collins",
        "genre": "Dystopian",
        "description": "A televised death match in a future nation.",
        "isbn": "978-0439023481",
        "published_year": 2008,
    },
    {
        "title": "Atomic Habits",
        "author": "James Clear",
        "genre": "Self-Help",
        "description": "Tiny changes, remarkable results.",
        "isbn": "978-0735211292",
        "published_year": 2018,
    },
    {
        "title": "Deep Work",
        "author": "Cal Newport",
        "genre": "Self-Help",
        "description": "Rules for focused success in a distracted world.",
        "isbn": "978-1455586691",
        "published_year": 2016,
    },
    {
        "title": "The Lean Startup",
        "author": "Eric Ries",
        "genre": "Business",
        "description": "How constant innovation creates radically successful businesses.",
        "isbn": "978-0307887894",
        "published_year": 2011,
    },
    {
        "title": "Zero to One",
        "author": "Peter Thiel",
        "genre": "Business",
        "description": "Notes on startups, or how to build the future.",
        "isbn": "978-0804139298",
        "published_year": 2014,
    },
    {
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "genre": "Philosophy",
        "description": "Personal writings of the Roman Emperor on Stoic philosophy.",
        "isbn": "978-0140449334",
        "published_year": 180,
    },
    {
        "title": "The Art of War",
        "author": "Sun Tzu",
        "genre": "Philosophy",
        "description": "An ancient Chinese military treatise.",
        "isbn": "978-1590302255",
        "published_year": -500,
    },
    {
        "title": "Frankenstein",
        "author": "Mary Shelley",
        "genre": "Horror",
        "description": "A scientist creates a monstrous creature.",
        "isbn": "978-0486282114",
        "published_year": 1818,
    },
    {
        "title": "Dracula",
        "author": "Bram Stoker",
        "genre": "Horror",
        "description": "Count Dracula attempts to move from Transylvania to England.",
        "isbn": "978-0486411095",
        "published_year": 1897,
    },
    {
        "title": "The Shining",
        "author": "Stephen King",
        "genre": "Horror",
        "description": "A family heads to an isolated hotel for the winter.",
        "isbn": "978-0307743657",
        "published_year": 1977,
    },
    {
        "title": "Norwegian Wood",
        "author": "Haruki Murakami",
        "genre": "Literary Fiction",
        "description": "A nostalgic story of loss and sexuality.",
        "isbn": "978-0375704024",
        "published_year": 1987,
    },
    {
        "title": "One Hundred Years of Solitude",
        "author": "Gabriel García Márquez",
        "genre": "Magical Realism",
        "description": "The multi-generational Buendía family.",
        "isbn": "978-0060883287",
        "published_year": 1967,
    },
    {
        "title": "Catch-22",
        "author": "Joseph Heller",
        "genre": "Satire",
        "description": "A satirical war novel.",
        "isbn": "978-1451626650",
        "published_year": 1961,
    },
    {
        "title": "Slaughterhouse-Five",
        "author": "Kurt Vonnegut",
        "genre": "Science Fiction",
        "description": "Billy Pilgrim, an optometrist who becomes unstuck in time.",
        "isbn": "978-0385333849",
        "published_year": 1969,
    },
    {
        "title": "The Picture of Dorian Gray",
        "author": "Oscar Wilde",
        "genre": "Classic",
        "description": "A man sells his soul for eternal youth.",
        "isbn": "978-0486278070",
        "published_year": 1890,
    },
    {
        "title": "Jane Eyre",
        "author": "Charlotte Brontë",
        "genre": "Classic",
        "description": "The experiences of its eponymous heroine.",
        "isbn": "978-0142437209",
        "published_year": 1847,
    },
    {
        "title": "Wuthering Heights",
        "author": "Emily Brontë",
        "genre": "Classic",
        "description": "Passionate, destructive love between Heathcliff and Catherine.",
        "isbn": "978-0141439556",
        "published_year": 1847,
    },
    {
        "title": "The Count of Monte Cristo",
        "author": "Alexandre Dumas",
        "genre": "Adventure",
        "description": "A man wrongly imprisoned plots elaborate revenge.",
        "isbn": "978-0140449266",
        "published_year": 1844,
    },
    {
        "title": "Moby-Dick",
        "author": "Herman Melville",
        "genre": "Adventure",
        "description": "Captain Ahab's obsessive quest for the white whale.",
        "isbn": "978-0142437247",
        "published_year": 1851,
    },
    {
        "title": "War and Peace",
        "author": "Leo Tolstoy",
        "genre": "Historical Fiction",
        "description": "The French invasion of Russia and Napoleonic era.",
        "isbn": "978-0140447934",
        "published_year": 1869,
    },
    {
        "title": "Anna Karenina",
        "author": "Leo Tolstoy",
        "genre": "Classic",
        "description": "A married aristocrat's affair and its consequences.",
        "isbn": "978-0143035008",
        "published_year": 1877,
    },
    {
        "title": "The Brothers Karamazov",
        "author": "Fyodor Dostoevsky",
        "genre": "Classic",
        "description": "A father's murder and the moral responsibility of his sons.",
        "isbn": "978-0374528379",
        "published_year": 1880,
    },
    {
        "title": "Les Misérables",
        "author": "Victor Hugo",
        "genre": "Historical Fiction",
        "description": "Ex-convict Jean Valjean's journey of redemption.",
        "isbn": "978-0451419439",
        "published_year": 1862,
    },
    {
        "title": "Don Quixote",
        "author": "Miguel de Cervantes",
        "genre": "Classic",
        "description": "The adventures of a nobleman who reads too many chivalric romances.",
        "isbn": "978-0060934347",
        "published_year": 1605,
    },
]

SAMPLE_USERS = [
    {"email": "admin@bookrec.com", "username": "admin", "password": "Admin@123456", "role": UserRole.ADMIN},
    {"email": "alice@example.com", "username": "alice", "password": "Alice@123456", "role": UserRole.USER},
    {"email": "bob@example.com", "username": "bob", "password": "Bob@1234567", "role": UserRole.USER},
    {"email": "carol@example.com", "username": "carol", "password": "Carol@123456", "role": UserRole.USER},
    {"email": "dave@example.com", "username": "dave", "password": "Dave@1234567", "role": UserRole.USER},
]


async def seed():
    """Seed the database with sample data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        # Create users
        users = []
        for u in SAMPLE_USERS:
            user = User(
                email=u["email"],
                username=u["username"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            session.add(user)
            users.append(user)
        await session.flush()
        print(f"Created {len(users)} users")

        # Create books
        books = []
        for b in SAMPLE_BOOKS:
            book = Book(**b)
            session.add(book)
            books.append(book)
        await session.flush()
        print(f"Created {len(books)} books")

        # Create random interactions
        interaction_types = list(InteractionType)
        count = 0
        for user in users[1:]:  # Skip admin
            num_interactions = random.randint(15, 40)
            sampled_books = random.sample(books, min(num_interactions, len(books)))
            for book in sampled_books:
                itype = random.choice(interaction_types)
                rating = round(random.uniform(1.0, 5.0), 1) if itype == InteractionType.RATE else None
                interaction = UserBookInteraction(
                    user_id=user.id,
                    book_id=book.id,
                    interaction_type=itype,
                    rating=rating,
                )
                session.add(interaction)
                count += 1
        await session.flush()
        print(f"Created {count} interactions")

        await session.commit()
        print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
